"""One live deepseek-flash call. The gate runs this file once."""

from __future__ import annotations

import json
import os

import pytest

from proofsmith.agent.loop import RESEND_REASONING
from proofsmith.agent.smoke import SMOKE_RUN_ID, run_smoke
from proofsmith.config import RUNS
from proofsmith.ledger import LEDGER_PATH, Ledger

pytestmark = pytest.mark.live


def _key_leaked(text: str) -> bool:
    key = os.environ.get("DEEPSEEK_API_KEY", "")
    if len(key) < 8:
        raise AssertionError("DEEPSEEK_API_KEY is not set")
    return key[:8] in text


def test_live_smoke_finds_mutex_members():
    ledger = Ledger(LEDGER_PATH)
    before = ledger.spent_usd()
    if before >= 0.10:
        pytest.fail(f"phase ceiling already reached: spent ${before:.6f}")

    result = run_smoke()
    summary = str(result.final.get("summary") or "")
    assert result.status == "finished", result.final
    assert "book_mtx_" in summary
    assert "risk_mtx_" in summary
    assert result.steps >= 2
    assert result.cost_usd > 0
    assert result.cost_usd < 0.02

    spent = ledger.spent_usd()
    assert spent <= 0.10, spent
    assert spent > before

    trajectory_path = RUNS / SMOKE_RUN_ID / "trajectory.jsonl"
    text = trajectory_path.read_text(encoding="utf-8")
    assert _key_leaked(text) is False, "API key prefix appeared in trajectory"
    events = [json.loads(line) for line in text.splitlines() if line.strip()]
    seen_result = False
    round_trip = False
    for event in events:
        if event.get("type") == "tool_result":
            seen_result = True
        elif event.get("type") == "llm_request" and seen_result:
            round_trip = True
        if event.get("type") == "llm_request" and not RESEND_REASONING:
            for message in event.get("messages") or []:
                assert "reasoning_content" not in message
    assert round_trip, "expected a tool result followed by another model request"
