"""FakeLLM replays scripted responses and does not open a socket."""

from __future__ import annotations

import socket

from proofsmith.llm import FakeLLM, LLMResponse, Usage


def test_fake_llm_records_requests_without_network(monkeypatch):
    def explode(*_args, **_kwargs):
        raise AssertionError("socket opened")

    monkeypatch.setattr(socket, "socket", explode)
    usage = Usage(3, 4, 1, 2)
    scripted = LLMResponse("hi", None, [], usage, "stop", {})
    llm = FakeLLM([scripted])
    messages = [{"role": "user", "content": "ping"}]
    got = llm.chat(messages, None, 32)
    assert got is scripted
    assert llm.requests == [{"messages": messages, "tools": None, "max_tokens": 32}]
