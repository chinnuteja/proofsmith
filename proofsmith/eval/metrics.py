"""Paired benchmark metrics. Missing runs never become failed observations."""
from __future__ import annotations

import math
import statistics
from collections import Counter

SYSTEMS = ("b0", "b1", "proofsmith")


def wilson(successes: int, total: int) -> list[float] | None:
    if not total:
        return None
    z = 1.959963984540054
    p = successes / total
    denominator = 1 + z * z / total
    centre = (p + z * z / (2 * total)) / denominator
    radius = z * math.sqrt(p * (1 - p) / total + z * z / (4 * total * total)) / denominator
    return [max(0.0, centre - radius), min(1.0, centre + radius)]


def mcnemar(b: int, c: int) -> float:
    n = b + c
    return min(1.0, 2 * sum(math.comb(n, i) for i in range(min(b, c) + 1)) / 2**n) if n else 1.0


def _rate(count: int, n: int) -> dict:
    return {"count": count, "pct": 100 * count / n if n else None, "ci95": wilson(count, n)}


def summarize(rows: list[dict], expected: dict[str, list[str]]) -> dict:
    """Compute all metrics against a frozen expected population, by track."""
    index = {}
    for row in rows:
        key = (row["track"], row["instance_id"], row["system"])
        if key in index:
            raise ValueError(f"duplicate verdict {key}")
        if row["instance_id"] not in expected.get(row["track"], []) or row["system"] not in SYSTEMS:
            raise ValueError(f"verdict outside protocol {key}")
        index[key] = row
    tracks = {}
    all_complete = True
    for track, ids in expected.items():
        systems = {}
        complete = all((track, name, system) in index for name in ids for system in SYSTEMS)
        all_complete = all_complete and complete
        for system in SYSTEMS:
            observed = [index[track, name, system] for name in ids if (track, name, system) in index]
            raw = sum(bool(r.get("f2p")) for r in observed)
            strict = sum(bool(r.get("f2p") and r.get("alignment", {}).get("strict")) for r in observed)
            relaxed = sum(bool(r.get("f2p") and r.get("alignment", {}).get("relaxed")) for r in observed)
            submitted = [r for r in observed if r.get("bundle_status") in {"submitted", "accepted"}]
            flaking = sum(0 < r.get("fixed_fails", 0) < r.get("n", 0) for r in submitted)
            oracles = Counter(r.get("oracle") or r.get("variant") or "unknown" for r in observed if r.get("f2p"))
            systems[system] = {
                "n_instances": len(observed), "expected_instances": len(ids), "missing": len(ids) - len(observed),
                "raw_f2p": _rate(raw, len(observed)), "aligned_f2p_strict": _rate(strict, len(observed)),
                "aligned_f2p_relaxed": _rate(relaxed, len(observed)),
                "alignment_unknown": sum(bool(r.get("alignment", {}).get("unknown")) for r in observed),
                "abstentions": sum(r.get("bundle_status") == "abstained" for r in observed),
                "errors": sum(bool(r.get("error")) for r in observed),
                "flake_on_fixed": _rate(flaking, len(submitted)), "per_oracle": dict(oracles),
                "median_cost_usd": statistics.median(r.get("cost_usd", 0) for r in observed) if observed else None,
                "median_wall_s": statistics.median(r.get("wall_s", 0) for r in observed) if observed else None,
            }
        b = c = paired = abstained = abstained_with_baseline = correct_abstentions = 0
        for name in ids:
            proof = index.get((track, name, "proofsmith"))
            baseline = index.get((track, name, "b1"))
            if proof and proof.get("bundle_status") == "abstained":
                abstained += 1
                if baseline:
                    abstained_with_baseline += 1
                    correct_abstentions += not bool(baseline.get("f2p"))
            if not proof or not baseline:
                continue
            paired += 1
            ps = bool(proof.get("f2p") and proof.get("alignment", {}).get("strict"))
            bs = bool(baseline.get("f2p") and baseline.get("alignment", {}).get("strict"))
            b += ps and not bs
            c += bs and not ps
        if not complete:
            verdict = "INCOMPLETE"
        elif any(s["alignment_unknown"] for s in systems.values()):
            verdict = "ALIGNMENT_UNRESOLVED"
        elif track == "B":
            lift = systems["proofsmith"]["aligned_f2p_strict"]["pct"] - systems["b1"]["aligned_f2p_strict"]["pct"]
            verdict = "PASS" if lift >= 20 - 1e-9 else "KILL_OR_RETHINK"
        else:
            lift = systems["proofsmith"]["raw_f2p"]["pct"] - systems["b1"]["raw_f2p"]["pct"]
            verdict = "OK" if lift >= -5 - 1e-9 else "RESTRICT_TO_LIFETIME_CONCURRENCY"
        tracks[track] = {
            "complete": complete, "systems": systems, "verdict": verdict,
            "comparison": {"paired": paired, "proofsmith_only": b, "b1_only": c, "mcnemar_p": mcnemar(b, c)},
            "abstention_precision": {"total": abstained, "paired": abstained_with_baseline,
                "correct": correct_abstentions, "value": correct_abstentions / abstained_with_baseline if abstained_with_baseline else None},
        }
    return {"schema": "proofsmith.summary/1", "complete": all_complete, "tracks": tracks}


def compute_metrics() -> dict:
    import json
    from proofsmith.eval.protocol import PROTOCOL_PATH
    from proofsmith.eval.runner import write_summary

    return write_summary(json.loads(PROTOCOL_PATH.read_text()))
