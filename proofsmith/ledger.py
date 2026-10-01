"""Append-only spend ledger. Every model request checks this first."""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING

from proofsmith.config import API_BASE, MAX_USD, REPO, RUNS

if TYPE_CHECKING:
    from proofsmith.llm import Usage

PRICING_PATH = REPO / "config" / "pricing.json"
LEDGER_PATH = RUNS / "ledger.jsonl"
_PRICE_KEYS = (
    "input_cache_hit_per_mtok",
    "input_cache_miss_per_mtok",
    "output_per_mtok",
)


class BudgetExceeded(RuntimeError):
    """Raised when recorded spend has reached PROOFSMITH_MAX_USD."""


def _load_pricing() -> dict:
    return json.loads(PRICING_PATH.read_text(encoding="utf-8"))


def _listed_prices(pricing: dict) -> list[float]:
    found: list[float] = []
    for row in (pricing.get("models") or {}).values():
        if not isinstance(row, dict):
            continue
        for key in _PRICE_KEYS:
            value = row.get(key)
            if isinstance(value, (int, float)) and not isinstance(value, bool):
                found.append(float(value))
    return found


def _rate(value: object, highest: float) -> float:
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return float(value)
    return highest


def cost_usd(model: str, usage: Usage, pricing: dict | None = None) -> float:  # noqa: F821
    """Price a usage record from config/pricing.json.

    Missing models and null fields use the highest listed per-million-token
    price so unknown tokens are never undercounted.
    """
    table = pricing if pricing is not None else _load_pricing()
    listed = _listed_prices(table)
    if not listed:
        raise RuntimeError("config/pricing.json has no numeric prices")
    highest = max(listed)
    row = (table.get("models") or {}).get(model)
    if not isinstance(row, dict):
        row = {}
    hit = _rate(row.get("input_cache_hit_per_mtok"), highest)
    miss = _rate(row.get("input_cache_miss_per_mtok"), highest)
    output = _rate(row.get("output_per_mtok"), highest)
    cache_hit = max(0, int(usage.cache_hit_tokens))
    prompt = max(0, int(usage.prompt_tokens))
    completion = max(0, int(usage.completion_tokens))
    miss_tokens = max(0, prompt - cache_hit)
    total = cache_hit * hit + miss_tokens * miss + completion * output
    return total / 1_000_000


class Ledger:
    def __init__(self, path: Path):
        self.path = Path(path)

    def spent_usd(self) -> float:
        if not self.path.is_file():
            return 0.0
        total = 0.0
        for line in self.path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            total += float(json.loads(line)["cost_usd"])
        return total

    def ensure_budget(self) -> None:
        spent = self.spent_usd()
        if spent >= MAX_USD:
            raise BudgetExceeded(f"spent ${spent:.6f} >= cap ${MAX_USD:.2f}")

    def record(self, run_id: str, model: str, usage: Usage) -> float:  # noqa: F821
        cost = cost_usd(model, usage)
        row = {
            "ts": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "run_id": run_id,
            "model": model,
            "usage": asdict(usage),
            "cost_usd": cost,
        }
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("a", encoding="utf-8", newline="\n") as handle:
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")
        return cost


def live_balance() -> str | None:
    """Return the USD total from GET /user/balance, or None if it cannot be read."""
    key = os.environ.get("DEEPSEEK_API_KEY", "")
    if not key:
        return None
    request = urllib.request.Request(
        f"{API_BASE}/user/balance",
        headers={"Authorization": f"Bearer {key}", "Accept": "application/json"},
        method="GET",
    )
    try:
        with urllib.request.urlopen(request, timeout=20) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, OSError):
        return None
    infos = payload.get("balance_infos") if isinstance(payload, dict) else None
    if not isinstance(infos, list):
        return None
    chosen = None
    for info in infos:
        if not isinstance(info, dict):
            continue
        if info.get("currency") == "USD":
            chosen = info
            break
        if chosen is None:
            chosen = info
    if not chosen or chosen.get("total_balance") is None:
        return None
    return str(chosen["total_balance"])


def print_status(path: Path | None = None) -> None:
    ledger = Ledger(path or LEDGER_PATH)
    spent = ledger.spent_usd()
    remaining = MAX_USD - spent
    print(f"spent: ${spent:.6f}")
    print(f"cap: ${MAX_USD:.2f}")
    print(f"remaining: ${remaining:.6f}")
    balance = live_balance()
    if balance is None:
        print("balance: unreachable")
    else:
        print(f"balance: ${balance}")
