"""A provisional estimate from historical spend, never labelled a completed pilot."""
import json
import statistics

from proofsmith import config
from proofsmith.eval.runner import atomic_json
from proofsmith.ledger import Ledger, LEDGER_PATH


def estimate(protocol: dict) -> dict:
    samples = []
    for track in ("A", "B"):
        for p in (config.RESULTS / "eval" / track).glob("*/*.json"):
            row = json.loads(p.read_text())
            if "cost_usd" in row:
                samples.append((p.relative_to(config.REPO).as_posix(), row))
    by_system = {}
    total_pilot = 0
    total_full = 0
    for system in ("b0", "b1", "proofsmith"):
        selected = [(p, r) for p, r in samples if r["system"] == system]
        proxy = None
        if not selected and system == "b0":
            selected = [(p, r) for p, r in samples if r["system"] == "b1"]
            proxy = "b1 exploratory samples; no real b0 pilot observation"
        mean = statistics.mean(r["cost_usd"] for _, r in selected) if selected else None
        pilot_pairs = sum(len(v) for v in protocol["pilot"].values())
        full_pairs = sum(len(v) for v in protocol["tracks"].values())
        by_system[system] = {"sample_count": len(selected), "source_files": [p for p, _ in selected],
            "proxy": proxy, "mean_cost_usd": mean, "pilot_pairs": pilot_pairs, "full_pairs": full_pairs,
            "pilot_estimate_usd": mean * pilot_pairs * 1.3 if mean is not None else None,
            "full_estimate_usd": mean * full_pairs * 1.3 if mean is not None else None}
        if mean is not None:
            total_pilot += mean * pilot_pairs * 1.3
            total_full += mean * full_pairs * 1.3
    spent = Ledger(LEDGER_PATH).spent_usd()
    payload = {"schema": "proofsmith.preflight/1", "provisional": True,
        "limitation": "Historical Track B samples only; ordinary bugs and the corrected pipeline may cost differently. This is not the pilot.",
        "systems": by_system, "safety_multiplier": 1.3, "pilot_estimate_usd": total_pilot,
        "full_estimate_usd": total_full, "recorded_spend_usd": spent, "cap_usd": config.MAX_USD,
        "remaining_cap_usd": max(0, config.MAX_USD - spent)}
    atomic_json(config.RESULTS / "preflight.json", payload)
    return payload
