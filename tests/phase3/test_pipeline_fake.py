"""Scripted Proofsmith runs against the real orderd build."""

from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest

from proofsmith.agent.loop import Budget
from proofsmith.config import MAX_STEPS, MAX_TOTAL_TOKENS, MAX_WALL_S, REPO
from proofsmith.datasets.schema import Instance
from proofsmith.freeze import load_bundle
from proofsmith.llm import FakeLLM, LLMResponse, ToolCall, Usage
from proofsmith.pipeline import make_verifier

pytestmark = [pytest.mark.slow, pytest.mark.timeout(1800)]

_FULL = Budget(MAX_STEPS, MAX_TOTAL_TOKENS, MAX_WALL_S)


def _reply(content: str | None, calls: list[ToolCall], usage: Usage | None = None) -> LLMResponse:
    return LLMResponse(
        content=content,
        reasoning_content=None,
        tool_calls=calls,
        usage=usage or Usage(8, 8, 0, 0),
        finish_reason="tool_calls" if calls else "stop",
    )


def _classify(oracles: list[str], usage: Usage | None = None) -> LLMResponse:
    payload = {"oracles": oracles, "rationale": "the report is observable", "suspects": []}
    return _reply(json.dumps(payload), [], usage)


def _orderd() -> Instance:
    return Instance.model_validate_json((REPO / "cases" / "orderd" / "instance.json").read_text(encoding="utf-8"))


def _harness_calls() -> list[ToolCall]:
    root = REPO / "cases" / "orderd" / "reference_harness"
    return [
        ToolCall("w1", "write_file", {"path": "proofsmith_harness/build.sh", "content": (root / "build.sh").read_text(encoding="utf-8")}),
        ToolCall("w2", "write_file", {"path": "proofsmith_harness/harness.cpp", "content": (root / "harness.cpp").read_text(encoding="utf-8")}),
        ToolCall("f", "finish", {"variant": "tsan", "summary": "two paths, one after the other"}),
    ]


def test_reference_harness_is_accepted(tmp_path: Path):
    llm = FakeLLM([_classify(["tsan"]), _reply(None, _harness_calls())])
    result = make_verifier(_orderd(), llm, _FULL, tmp_path / "bundle")
    assert result.status == "accepted", result.reason
    assert result.oracle == "tsan"
    assert result.signature is not None
    assert result.signature.split("|", 1)[0] == "tsan:lock-order-inversion"
    loaded = load_bundle(result.bundle_dir)
    assert loaded["signature"].split("|", 1)[0] == "tsan:lock-order-inversion"


def test_harness_only_race_is_rejected_then_abstains(tmp_path: Path):
    source = """#include <thread>
int counter = 0;
void bump() {
  for (int i = 0; i < 1000; ++i) ++counter;
}
int main() {
  std::thread a(bump);
  std::thread b(bump);
  a.join();
  b.join();
  return 0;
}
"""
    script = """#!/usr/bin/env bash
set -euo pipefail
mkdir -p "$PS_OUT"
# shellcheck disable=SC2086
"$PS_CXX" $PS_CXXFLAGS -std=c++17 -pthread \\
  "$PS_REPO/proofsmith_harness/harness.cpp" \\
  $PS_LDFLAGS -pthread \\
  -o "$PS_OUT/harness"
"""
    llm = FakeLLM(
        [
            _classify(["tsan"]),
            _reply(
                None,
                [
                    ToolCall("w1", "write_file", {"path": "proofsmith_harness/build.sh", "content": script}),
                    ToolCall("w2", "write_file", {"path": "proofsmith_harness/harness.cpp", "content": source}),
                    ToolCall("f", "finish", {"variant": "tsan", "summary": "race"}),
                ],
            ),
            _reply(None, [ToolCall("a", "abstain", {"reason": "the report is not in the harness"})]),
        ]
    )
    result = make_verifier(_orderd(), llm, _FULL, tmp_path / "bundle")
    assert result.status == "abstained", result.reason
    assert "no eligible" in result.reason


def test_edit_outside_harness_is_rejected(tmp_path: Path):
    llm = FakeLLM(
        [
            _classify(["tsan"]),
            _reply(
                None,
                [
                    ToolCall("s", "run_shell", {"cmd": "printf 'int extra = 1;\\n' >> order_book.cpp", "timeout_s": 30}),
                    ToolCall("f", "finish", {"variant": "tsan", "summary": "edited"}),
                ],
            ),
            _reply(None, [ToolCall("a", "abstain", {"reason": "cannot touch the project"})]),
        ]
    )
    result = make_verifier(_orderd(), llm, _FULL, tmp_path / "bundle")
    assert result.status != "accepted"
    blob = result.reason + " " + " ".join(str(item.get("reason")) for item in result.attempts)
    assert "harness modified files outside proofsmith_harness/" in blob


def test_existing_failing_test_is_skipped(tmp_path: Path):
    copied = tmp_path / "buggy"
    shutil.copytree(REPO / "cases" / "orderd" / "buggy", copied)
    test = copied / "tests" / "book_ops.cpp"
    text = test.read_text(encoding="utf-8").replace("int main() {", "int main() { return 1;", 1)
    test.write_text(text, encoding="utf-8", newline="\n")
    instance = _orderd().model_copy(update={"source": _orderd().source.model_copy(update={"path": str(copied)})})
    llm = FakeLLM([])
    result = make_verifier(instance, llm, _FULL, tmp_path / "bundle")
    assert result.status == "skipped"
    assert result.reason == "existing test already fails; Proofsmith not needed"
    assert llm.requests == []


def test_budget_is_shared_across_oracles(tmp_path: Path):
    llm = FakeLLM(
        [
            _classify(["tsan", "asan_ubsan"], Usage(5, 5, 0, 0)),
            _reply(None, [ToolCall("1", "list_dir", {"path": "."})], Usage(100, 0, 0, 0)),
            _reply(None, [ToolCall("2", "list_dir", {"path": "."})], Usage(100, 0, 0, 0)),
        ]
    )
    result = make_verifier(_orderd(), llm, Budget(MAX_STEPS, 30, MAX_WALL_S), tmp_path / "bundle")
    assert result.status == "abstained", result.reason
    assert "budget" in result.reason
    assert len(llm.requests) == 0
