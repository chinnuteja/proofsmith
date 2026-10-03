"""B0, B1, and Proofsmith share tools and budget. No live model."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from proofsmith.agent.loop import Budget
from proofsmith.config import REPO
from proofsmith.datasets.schema import Instance
from proofsmith.freeze import load_bundle
from proofsmith.llm import FakeLLM, LLMResponse, ToolCall, Usage
import proofsmith.pipeline as pipeline
import proofsmith.systems as systems

pytestmark = [pytest.mark.slow, pytest.mark.timeout(900)]


def _reply(content: str | None, calls: list[ToolCall]) -> LLMResponse:
    return LLMResponse(content, None, calls, Usage(0, 0, 0, 0), "tool_calls" if calls else "stop")


def _classify() -> LLMResponse:
    payload = {"oracles": ["assertion"], "rationale": "the report is observable", "suspects": []}
    return _reply(json.dumps(payload), [])


def _orderd() -> Instance:
    return Instance.model_validate_json((REPO / "cases" / "orderd" / "instance.json").read_text(encoding="utf-8"))


def _harness_calls(variant: str) -> list[ToolCall]:
    script = """#!/usr/bin/env bash
set -euo pipefail
mkdir -p "$PS_OUT"
"$PS_CXX" $PS_CXXFLAGS -std=c++17 "$PS_REPO/proofsmith_harness/harness.cpp" $PS_LDFLAGS -o "$PS_OUT/harness"
"""
    source = "int main() { return 1; }\n"
    return [
        ToolCall("w1", "write_file", {"path": "proofsmith_harness/build.sh", "content": script}),
        ToolCall("w2", "write_file", {"path": "proofsmith_harness/harness.cpp", "content": source}),
        ToolCall("f", "finish", {"variant": variant, "summary": "reproduction is ready"}),
    ]


def _schemas(llm: FakeLLM) -> list:
    for request in llm.requests:
        if request["tools"]:
            return request["tools"]
    raise AssertionError("no tool schema was sent")


def _prompt(llm: FakeLLM) -> str:
    for request in llm.requests:
        if request["tools"]:
            return request["messages"][0]["content"]
    raise AssertionError("no system prompt was sent")


def test_systems_share_schemas_budgets_and_freeze_b0(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    seen: list[Budget] = []
    real_pipeline = pipeline.run_agent
    real_systems = systems.run_agent

    def wrap(fn):
        def inner(*args, **kwargs):
            seen.append(args[4])
            return fn(*args, **kwargs)

        return inner

    monkeypatch.setattr(pipeline, "run_agent", wrap(real_pipeline))
    monkeypatch.setattr(systems, "run_agent", wrap(real_systems))
    budget = Budget(8, 40000, 120)
    instance = _orderd()
    b0 = FakeLLM([_reply(None, _harness_calls("plain"))])
    b1 = FakeLLM([_reply(None, _harness_calls("asan_ubsan"))])
    proof = FakeLLM([_classify(), _reply(None, [ToolCall("a", "abstain", {"reason": "stop"})])])

    b0_dir = systems.run_system("b0", instance, b0, budget, tmp_path / "b0")
    b1_dir = systems.run_system("b1", instance, b1, budget, tmp_path / "b1")
    systems.run_system("proofsmith", instance, proof, budget, tmp_path / "proofsmith")

    assert json.dumps(_schemas(b0), sort_keys=True) == json.dumps(_schemas(b1), sort_keys=True)
    assert json.dumps(_schemas(b0), sort_keys=True) == json.dumps(_schemas(proof), sort_keys=True)
    assert "Reproduce first" not in _prompt(b0)
    assert "Reproduce first" in _prompt(b1)
    assert "harness_contract" not in _prompt(b0)
    assert "proofsmith_harness/build.sh" in _prompt(b0)
    assert "proofsmith_harness/build.sh" in _prompt(b1)

    assert len(seen) == 3
    b0_budget, b1_budget, proof_budget = seen
    assert (b0_budget.max_steps, b0_budget.max_total_tokens, b0_budget.max_wall_s) == (8, 40000, 120)
    assert (b1_budget.max_steps, b1_budget.max_total_tokens, b1_budget.max_wall_s) == (8, 40000, 120)
    # The classifier consumed one of the shared eight steps. Giving the
    # child eight more would grant Proofsmith an unfair extra model call.
    assert (proof_budget.max_steps, proof_budget.max_total_tokens) == (7, 40000)
    assert proof_budget.max_steps + len([r for r in proof.requests if r["tools"] is None]) == budget.max_steps

    loaded = load_bundle(b0_dir)
    assert loaded["status"] == "submitted"
    assert loaded["variant"] == "plain"
    assert loaded["system"] == "b0"
    assert load_bundle(b1_dir)["system"] == "b1"
