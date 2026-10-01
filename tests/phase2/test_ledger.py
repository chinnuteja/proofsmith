"""Spend ledger prices tokens from the fetched pricing table."""

from __future__ import annotations

import json

import pytest

from proofsmith.config import REPO
from proofsmith.ledger import BudgetExceeded, Ledger, cost_usd
from proofsmith.llm import Usage


def test_pricing_file_records_peak_rates():
    data = json.loads((REPO / "config" / "pricing.json").read_text(encoding="utf-8"))
    assert data["source_url"] == "https://api-docs.deepseek.com/quick_start/pricing"
    assert data["fetched"] == "2026-10-01"
    assert data["currency"] == "USD"
    flash = data["models"]["deepseek-flash"]
    pro = data["models"]["deepseek-v4-pro"]
    assert flash["input_cache_hit_per_mtok"] == 0.006
    assert flash["input_cache_miss_per_mtok"] == 0.3
    assert flash["output_per_mtok"] == 1.2
    assert pro["input_cache_hit_per_mtok"] == 0.044
    assert pro["input_cache_miss_per_mtok"] == 1.32
    assert pro["output_per_mtok"] == 3.96


def test_known_usage_matches_pricing_to_1e9(tmp_path):
    usage = Usage(
        prompt_tokens=1_000_000,
        completion_tokens=1_000_000,
        reasoning_tokens=0,
        cache_hit_tokens=250_000,
    )
    # 250000 * 0.006 + 750000 * 0.3 + 1000000 * 1.2 = 1.4265
    expected = 1.4265
    assert abs(cost_usd("deepseek-flash", usage) - expected) < 1e-9
    ledger = Ledger(tmp_path / "ledger.jsonl")
    recorded = ledger.record("run-a", "deepseek-flash", usage)
    assert abs(recorded - expected) < 1e-9
    assert abs(ledger.spent_usd() - expected) < 1e-9
    again = ledger.record("run-b", "deepseek-flash", Usage(0, 0, 0, 0))
    assert again == 0.0
    assert abs(ledger.spent_usd() - expected) < 1e-9


def test_ensure_budget_raises_at_cap(monkeypatch, tmp_path):
    monkeypatch.setattr("proofsmith.ledger.MAX_USD", 0.0)
    ledger = Ledger(tmp_path / "ledger.jsonl")
    with pytest.raises(BudgetExceeded):
        ledger.ensure_budget()


def test_ensure_budget_allows_spend_under_cap(monkeypatch, tmp_path):
    monkeypatch.setattr("proofsmith.ledger.MAX_USD", 1.0)
    ledger = Ledger(tmp_path / "ledger.jsonl")
    ledger.ensure_budget()


def test_unknown_model_uses_highest_listed_price():
    usage = Usage(prompt_tokens=1_000_000, completion_tokens=0, reasoning_tokens=0, cache_hit_tokens=0)
    assert abs(cost_usd("not-a-listed-model", usage) - 3.96) < 1e-9


def test_null_price_uses_highest_listed_price(monkeypatch):
    monkeypatch.setattr(
        "proofsmith.ledger._load_pricing",
        lambda: {
            "models": {
                "partial": {
                    "input_cache_hit_per_mtok": 1.0,
                    "input_cache_miss_per_mtok": None,
                    "output_per_mtok": 2.0,
                }
            }
        },
    )
    usage = Usage(prompt_tokens=1_000_000, completion_tokens=0, reasoning_tokens=0, cache_hit_tokens=0)
    assert abs(cost_usd("partial", usage) - 2.0) < 1e-9
