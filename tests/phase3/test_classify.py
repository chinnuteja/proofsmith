"""Classifier parsing, filtering, and the two-strike fallback."""

from __future__ import annotations

import json

from proofsmith.llm import FakeLLM, LLMResponse, Usage
from proofsmith.pipeline import classify


def _reply(content: str, usage: Usage | None = None) -> LLMResponse:
    return LLMResponse(
        content=content,
        reasoning_content=None,
        tool_calls=[],
        usage=usage or Usage(4, 4, 0, 0),
        finish_reason="stop",
    )


def test_valid_json_is_parsed():
    payload = {
        "oracles": ["assertion", "tsan"],
        "rationale": "the report names an input and a result",
        "suspects": ["convert"],
    }
    llm = FakeLLM([_reply(json.dumps(payload))])
    result = classify({"title": "wrong value", "body": "input 1 gives 2"}, "files: a.cpp", llm)
    assert result.oracles == ["assertion", "tsan"]
    assert result.rationale == payload["rationale"]
    assert result.suspects == ["convert"]
    assert len(llm.requests) == 1


def test_invalid_json_twice_uses_fallback_order():
    llm = FakeLLM([_reply("not json"), _reply("still not json")])
    result = classify({"title": "t", "body": "b"}, "summary", llm)
    assert result.oracles == ["asan_ubsan", "tsan"]
    assert len(llm.requests) == 2


def test_unknown_oracle_names_are_filtered():
    payload = {
        "oracles": ["tsan", "magic", "assertion", "asan_ubsan"],
        "rationale": "keep the known ones",
        "suspects": [],
    }
    llm = FakeLLM([_reply(json.dumps(payload))])
    result = classify({"title": "t", "body": "b"}, "summary", llm)
    assert result.oracles == ["tsan", "assertion"]


def test_result_is_capped_at_two():
    payload = {
        "oracles": ["assertion", "tsan", "asan_ubsan"],
        "rationale": "too many",
        "suspects": ["a", "b"],
    }
    llm = FakeLLM([_reply(json.dumps(payload))])
    result = classify({"title": "t", "body": "b"}, "summary", llm)
    assert result.oracles == ["assertion", "tsan"]
    assert len(result.oracles) == 2
