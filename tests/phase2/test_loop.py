"""Scripted agent loop: finish, budgets, nudges, and no leaked API key."""

from __future__ import annotations

import json
import os
from pathlib import Path

from proofsmith.agent.loop import NUDGE, Budget, run_agent
from proofsmith.agent.tools import ToolSet
from proofsmith.config import MAX_STEPS, MAX_TOTAL_TOKENS, MAX_WALL_S
from proofsmith.datasets.schema import BuildRecipe
from proofsmith.llm import FakeLLM, LLMResponse, ToolCall, Usage
from proofsmith.sandbox import Sandbox


def _key_leaked(text: str) -> bool:
    key = os.environ.get("DEEPSEEK_API_KEY", "")
    if len(key) < 8:
        raise AssertionError("DEEPSEEK_API_KEY is not set")
    return key[:8] in text


def _response(calls: list[ToolCall], usage: Usage | None = None, content: str | None = None) -> LLMResponse:
    return LLMResponse(
        content=content,
        reasoning_content="REASONING_SENTINEL",
        tool_calls=calls,
        usage=usage or Usage(10, 5, 1, 0),
        finish_reason="tool_calls" if calls else "stop",
        raw={},
    )


def _tools(tmp_path: Path, run_id: str) -> tuple[Sandbox, ToolSet]:
    src = tmp_path / "src"
    src.mkdir()
    (src / "hello.txt").write_text("hello\n", encoding="utf-8")
    sandbox = Sandbox.create(src, run_id)
    recipe = BuildRecipe(system="custom", custom_script="true")
    tools = ToolSet(sandbox, recipe, tmp_path / "work")
    return sandbox, tools


def _events(run_dir: Path) -> list[dict]:
    path = run_dir / "trajectory.jsonl"
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def test_three_steps_finish_and_hide_key(tmp_path: Path, monkeypatch):
    sentinel = "S3NT1N3L-test-secret-not-a-real-key"
    monkeypatch.setenv("DEEPSEEK_API_KEY", sentinel)
    sandbox, tools = _tools(tmp_path, "phase2-loop-finish")
    try:
        llm = FakeLLM(
            [
                _response([ToolCall("1", "list_dir", {"path": "."})]),
                _response([ToolCall("2", "read_file", {"path": "hello.txt"})]),
                _response([ToolCall("3", "finish", {"variant": "plain", "summary": "done"})]),
            ]
        )
        run_dir = tmp_path / "run"
        result = run_agent(
            llm,
            "Inspect the tree.",
            "Read hello.txt and finish. Redact this sentinel in logs: " + sentinel,
            tools,
            Budget(MAX_STEPS, MAX_TOTAL_TOKENS, MAX_WALL_S),
            run_dir,
        )
        assert result.status == "finished"
        assert result.steps == 3
        assert result.final["summary"] == "done"
        blob = json.dumps(llm.requests)
        assert "REASONING_SENTINEL" not in blob
        assert "reasoning_content" not in blob
        events = _events(run_dir)
        assert sum(1 for event in events if event["type"] == "final") == 1
        trajectory = (run_dir / "trajectory.jsonl").read_text(encoding="utf-8")
        assert _key_leaked(trajectory) is False
        assert "[redacted]" in trajectory
        for event in events:
            if event["type"] != "llm_request":
                continue
            for message in event["messages"]:
                assert "reasoning_content" not in message
    finally:
        sandbox.destroy()


def test_step_cap_exhausts_at_50(tmp_path: Path):
    sandbox, tools = _tools(tmp_path, "phase2-loop-steps")
    try:
        calls = [_response([ToolCall(str(i), "list_dir", {"path": "."})]) for i in range(50)]
        llm = FakeLLM(calls)
        result = run_agent(
            llm,
            "system",
            "user",
            tools,
            Budget(50, MAX_TOTAL_TOKENS, MAX_WALL_S),
            tmp_path / "run",
        )
        assert result.status == "budget_exhausted"
        assert result.steps == 50
        assert len(llm.requests) == 50
        events = _events(tmp_path / "run")
        assert sum(1 for event in events if event["type"] == "final") == 1
    finally:
        sandbox.destroy()


def test_token_cap_exhausts(tmp_path: Path):
    sandbox, tools = _tools(tmp_path, "phase2-loop-tokens")
    try:
        llm = FakeLLM(
            [
                _response(
                    [ToolCall("1", "list_dir", {"path": "."})],
                    usage=Usage(400_000, 100_000, 0, 0),
                )
            ]
        )
        result = run_agent(
            llm,
            "system",
            "user",
            tools,
            Budget(MAX_STEPS, 500_000, MAX_WALL_S),
            tmp_path / "run",
        )
        assert result.status == "budget_exhausted"
        assert result.steps == 1
        assert len(llm.requests) == 1
    finally:
        sandbox.destroy()


def test_three_nudges_then_error(tmp_path: Path):
    sandbox, tools = _tools(tmp_path, "phase2-loop-nudge")
    try:
        llm = FakeLLM([_response([], content="no tool") for _ in range(4)])
        result = run_agent(
            llm,
            "system",
            "user",
            tools,
            Budget(MAX_STEPS, MAX_TOTAL_TOKENS, MAX_WALL_S),
            tmp_path / "run",
        )
        assert result.status == "error"
        assert result.steps == 4
        nudges = [
            message
            for message in llm.requests[-1]["messages"]
            if message.get("role") == "user" and message.get("content") == NUDGE
        ]
        assert len(nudges) == 3
        events = _events(tmp_path / "run")
        assert sum(1 for event in events if event["type"] == "final") == 1
    finally:
        sandbox.destroy()
