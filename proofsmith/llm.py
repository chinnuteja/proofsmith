"""DeepSeek client and a scripted fake with the same chat signature."""

from __future__ import annotations

import json
import os
import time
from dataclasses import dataclass, field

from openai import OpenAI

from proofsmith.config import API_BASE
from proofsmith.ledger import Ledger

_BACKOFF_S = (1, 2, 4, 8, 16)


@dataclass
class Usage:
    prompt_tokens: int
    completion_tokens: int
    reasoning_tokens: int
    cache_hit_tokens: int


@dataclass
class ToolCall:
    id: str
    name: str
    arguments: dict


@dataclass
class LLMResponse:
    content: str | None
    reasoning_content: str | None
    tool_calls: list[ToolCall]
    usage: Usage
    finish_reason: str
    raw: dict = field(default_factory=dict)


def _retriable(exc: BaseException) -> bool:
    status = getattr(exc, "status_code", None)
    if status is None:
        response = getattr(exc, "response", None)
        status = getattr(response, "status_code", None)
    if not isinstance(status, int):
        return False
    return status == 429 or status >= 500


def _as_int(value: object) -> int:
    if isinstance(value, bool) or value is None:
        return 0
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return int(value)
    return 0


def _usage_from_payload(payload: object) -> Usage:
    if not isinstance(payload, dict):
        return Usage(0, 0, 0, 0)
    completion_details = payload.get("completion_tokens_details") or {}
    prompt_details = payload.get("prompt_tokens_details") or {}
    if not isinstance(completion_details, dict):
        completion_details = {}
    if not isinstance(prompt_details, dict):
        prompt_details = {}
    cache_hit = payload.get("prompt_cache_hit_tokens")
    if cache_hit is None:
        cache_hit = prompt_details.get("cached_tokens")
    return Usage(
        prompt_tokens=_as_int(payload.get("prompt_tokens")),
        completion_tokens=_as_int(payload.get("completion_tokens")),
        reasoning_tokens=_as_int(completion_details.get("reasoning_tokens")),
        cache_hit_tokens=_as_int(cache_hit),
    )


def _parse_arguments(raw: object) -> dict:
    if isinstance(raw, dict):
        return raw
    if isinstance(raw, str):
        if not raw.strip():
            return {}
        try:
            parsed = json.loads(raw)
        except json.JSONDecodeError:
            return {"_unparsed": raw}
        if isinstance(parsed, dict):
            return parsed
        return {"_unparsed": raw}
    return {}


def parse_chat_response(response: object) -> LLMResponse:
    raw = response.model_dump() if hasattr(response, "model_dump") else {}
    choices = raw.get("choices") or []
    choice = choices[0] if choices else {}
    message = choice.get("message") or {}
    calls: list[ToolCall] = []
    for tool_call in message.get("tool_calls") or []:
        function = tool_call.get("function") or {}
        calls.append(
            ToolCall(
                id=str(tool_call.get("id") or ""),
                name=str(function.get("name") or ""),
                arguments=_parse_arguments(function.get("arguments")),
            )
        )
    return LLMResponse(
        content=message.get("content"),
        reasoning_content=message.get("reasoning_content"),
        tool_calls=calls,
        usage=_usage_from_payload(raw.get("usage")),
        finish_reason=str(choice.get("finish_reason") or ""),
        raw=raw,
    )


class LLMClient:
    def __init__(self, model: str, ledger: Ledger, run_id: str):
        self.model = model
        self.ledger = ledger
        self.run_id = run_id
        self.system_name = "agent"
        self.costs: list[float] = []
        key = os.environ.get("DEEPSEEK_API_KEY", "")
        if not key:
            raise RuntimeError("DEEPSEEK_API_KEY is not set")
        self._client = OpenAI(api_key=key, base_url=API_BASE, timeout=120.0)

    def chat(self, messages: list[dict], tools: list[dict] | None, max_tokens: int) -> LLMResponse:
        self.ledger.ensure_budget()
        kwargs: dict = {
            "model": self.model,
            "messages": messages,
            "max_tokens": max_tokens,
        }
        if tools:
            kwargs["tools"] = tools
        response = None
        for attempt in range(5):
            try:
                response = self._client.chat.completions.create(**kwargs)
                break
            except Exception as exc:
                if not _retriable(exc) or attempt == 4:
                    raise
                time.sleep(_BACKOFF_S[attempt])
        if response is None:
            raise RuntimeError("request failed")
        parsed = parse_chat_response(response)
        self.costs.append(self.ledger.record(self.run_id, self.model, parsed.usage))
        return parsed


class FakeLLM:
    """Scripted client. chat() never opens a socket."""

    def __init__(self, responses: list[LLMResponse]):
        self._responses = list(responses)
        self.requests: list[dict] = []
        self.model = ""
        self.costs: list[float] = []

    def chat(self, messages: list[dict], tools: list[dict] | None, max_tokens: int) -> LLMResponse:
        self.requests.append(
            {
                "messages": json.loads(json.dumps(messages)),
                "tools": tools,
                "max_tokens": max_tokens,
            }
        )
        if not self._responses:
            raise RuntimeError("FakeLLM has no scripted responses left")
        return self._responses.pop(0)
