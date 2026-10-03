"""One tool-calling loop shared by every system."""

from __future__ import annotations

import json
import os
import time
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path

from proofsmith.llm import LLMResponse, Usage
from proofsmith.ledger import BudgetExceeded

# Live round-trip rule. Stay False unless a real DeepSeek follow-up rejects
# the assistant message when reasoning_content is omitted. The phase log
# records which rule the smoke test proved.
RESEND_REASONING = False

NUDGE = "Use a tool. Call finish(...) or abstain(...) when done."
MAX_RESPONSE_TOKENS = 16384
_TERMINAL = {"finish", "abstain"}


@dataclass
class Budget:
    max_steps: int
    max_total_tokens: int
    max_wall_s: int


@dataclass
class AgentResult:
    status: str
    final: dict
    steps: int
    usage: Usage
    wall_s: float
    cost_usd: float


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _redact(value: object) -> object:
    key = os.environ.get("DEEPSEEK_API_KEY", "")
    if isinstance(value, str):
        if key and key in value:
            return value.replace(key, "[redacted]")
        return value
    if isinstance(value, list):
        return [_redact(item) for item in value]
    if isinstance(value, dict):
        cleaned = {}
        for name, item in value.items():
            if str(name).lower() == "authorization":
                continue
            cleaned[name] = _redact(item)
        return cleaned
    return value


def _emit(path: Path, event: dict) -> None:
    body = _redact(event)
    with path.open("a", encoding="utf-8", newline="\n") as handle:
        handle.write(json.dumps(body, ensure_ascii=False) + "\n")


def _add_usage(total: Usage, extra: Usage) -> Usage:
    return Usage(
        total.prompt_tokens + extra.prompt_tokens,
        total.completion_tokens + extra.completion_tokens,
        total.reasoning_tokens + extra.reasoning_tokens,
        total.cache_hit_tokens + extra.cache_hit_tokens,
    )


def _tokens(usage: Usage) -> int:
    return usage.prompt_tokens + usage.completion_tokens


def input_token_upper_bound(messages: list[dict], tools: list[dict] | None) -> int:
    """Conservative UTF-8 bound including serialized tools and chat framing."""
    return len(json.dumps({"messages": messages, "tools": tools}, ensure_ascii=False).encode("utf-8")) + 4096


def assistant_message(response: LLMResponse) -> dict:
    """Assistant turn sent back to the API.

    content and tool_calls are kept. reasoning_content is omitted unless
    RESEND_REASONING is set.
    """
    message: dict = {"role": "assistant", "content": response.content}
    if response.tool_calls:
        message["tool_calls"] = [
            {
                "id": call.id,
                "type": "function",
                "function": {
                    "name": call.name,
                    "arguments": json.dumps(call.arguments, ensure_ascii=False),
                },
            }
            for call in response.tool_calls
        ]
    if RESEND_REASONING and response.reasoning_content:
        message["reasoning_content"] = response.reasoning_content
    return message


def _cost(llm: object) -> float:
    costs = getattr(llm, "costs", None)
    if not costs:
        return 0.0
    return float(sum(costs))


def run_agent(
    llm,
    system_prompt: str,
    user_prompt: str,
    tools,
    budget: Budget,
    run_dir: Path,
    on_finish=None,
) -> AgentResult:
    run_dir = Path(run_dir)
    run_dir.mkdir(parents=True, exist_ok=True)
    trajectory = run_dir / "trajectory.jsonl"
    trajectory.write_text("", encoding="utf-8", newline="\n")
    messages: list[dict] = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt},
    ]
    usage = Usage(0, 0, 0, 0)
    started = time.monotonic()
    step = 0
    nudge_streak = 0
    schemas = tools.schemas()

    def end(status: str, final: dict, budget_reason: str | None = None) -> AgentResult:
        wall = time.monotonic() - started
        cost = _cost(llm)
        if budget_reason:
            _emit(trajectory, {"t": _now(), "step": step, "type": "budget", "reason": budget_reason})
        summary = {
            "run_id": run_dir.name,
            "system": getattr(llm, "system_name", "agent"),
            "instance_id": getattr(tools, "instance_id", "") or "",
            "status": status,
            "steps": step,
            "tokens": _tokens(usage),
            "cost_usd": cost,
            "wall_s": wall,
            "max_total_tokens": budget.max_total_tokens,
            "model": getattr(llm, "model", "") or "",
            "final": final,
        }
        _emit(
            trajectory,
            {
                "t": _now(),
                "step": step,
                "type": "final",
                "status": status,
                "final": final,
                "steps": step,
                "usage": asdict(usage),
                "wall_s": wall,
                "cost_usd": cost,
            },
        )
        (run_dir / "summary.json").write_text(
            json.dumps(summary, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
            newline="\n",
        )
        return AgentResult(status, final, step, usage, wall, cost)

    while True:
        if step >= budget.max_steps:
            return end("budget_exhausted", {}, "steps")
        if time.monotonic() - started >= budget.max_wall_s:
            return end("budget_exhausted", {}, "wall")
        if _tokens(usage) >= budget.max_total_tokens:
            return end("budget_exhausted", {}, "tokens")

        remaining = budget.max_total_tokens - _tokens(usage)
        completion_tokens = min(MAX_RESPONSE_TOKENS, remaining - input_token_upper_bound(messages, schemas))
        if completion_tokens <= 0:
            return end("budget_exhausted", {}, "tokens: next request cannot fit")

        step += 1
        _emit(
            trajectory,
            {
                "t": _now(),
                "step": step,
                "type": "llm_request",
                "model": getattr(llm, "model", "") or "",
                "max_tokens": completion_tokens,
                "messages": messages,
                "tools": schemas,
            },
        )
        try:
            response = llm.chat(messages, schemas, completion_tokens)
        except BudgetExceeded:
            end("interrupted", {"error": "global spending cap reached"})
            raise
        except Exception as exc:
            detail = f"{type(exc).__name__}: {exc}"
            _emit(trajectory, {"t": _now(), "step": step, "type": "llm_response", "error": detail})
            return end("error", {"error": detail})

        usage = _add_usage(usage, response.usage)
        _emit(
            trajectory,
            {
                "t": _now(),
                "step": step,
                "type": "llm_response",
                "content": response.content,
                "reasoning_content": response.reasoning_content,
                "tool_calls": [
                    {"id": call.id, "name": call.name, "arguments": call.arguments}
                    for call in response.tool_calls
                ],
                "usage": asdict(response.usage),
                "finish_reason": response.finish_reason,
            },
        )
        if _tokens(usage) > budget.max_total_tokens:
            return end("budget_exhausted", {}, "tokens: provider usage exceeded reservation")
        messages.append(assistant_message(response))

        calls_terminal = any(call.name in _TERMINAL for call in response.tool_calls)
        if _tokens(usage) >= budget.max_total_tokens and not calls_terminal:
            return end("budget_exhausted", {}, "tokens")

        if not response.tool_calls:
            if nudge_streak >= 3:
                return end("error", {"error": "model replied without a tool call"})
            nudge_streak += 1
            messages.append({"role": "user", "content": NUDGE})
            continue

        nudge_streak = 0
        terminal = None
        for call in response.tool_calls:
            _emit(
                trajectory,
                {
                    "t": _now(),
                    "step": step,
                    "type": "tool_call",
                    "id": call.id,
                    "name": call.name,
                    "arguments": call.arguments,
                },
            )
            output = tools.dispatch(call.name, call.arguments)
            _emit(
                trajectory,
                {
                    "t": _now(),
                    "step": step,
                    "type": "tool_result",
                    "id": call.id,
                    "name": call.name,
                    "output": output,
                },
            )
            messages.append({"role": "tool", "tool_call_id": call.id, "content": output})
            terminal = getattr(tools, "terminal", None)
            if terminal:
                break

        if terminal:
            if terminal.get("tool") == "finish":
                finished = dict(terminal)
                feedback = None
                if on_finish is not None:
                    feedback = on_finish(finished)
                    tools.terminal = None
                if feedback:
                    messages.append({"role": "user", "content": str(feedback)})
                    continue
                return end(
                    "finished",
                    {"variant": finished.get("variant"), "summary": finished.get("summary")},
                )
            return end("abstained", {"reason": terminal.get("reason")})

        if step >= budget.max_steps:
            return end("budget_exhausted", {}, "steps")
        if time.monotonic() - started >= budget.max_wall_s:
            return end("budget_exhausted", {}, "wall")
