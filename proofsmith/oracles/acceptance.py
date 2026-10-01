"""Decide whether a set of runs has a stable oracle signature."""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass

ELIGIBLE = {"tsan": ("tsan:",), "asan_ubsan": ("asan:", "ubsan:"), "assertion": ("assert",)}


@dataclass
class Decision:
    accepted: bool
    signature: str | None
    count: int
    n: int
    reason: str


def decide(runs, k, oracle):
    n = len(runs)
    prefixes = ELIGIBLE[oracle]
    counts = Counter()
    for r in runs:
        ev = r.evidence
        if not ev.kind.startswith(prefixes):
            continue
        if ev.kind != "assert" and not ev.app_frames:
            continue  # sanitizer report with no application frame = the harness is buggy, not the project
        counts[ev.signature] += 1
    if not counts:
        return Decision(False, None, 0, n, f"no eligible {oracle} evidence in {n} runs")
    sig, c = counts.most_common(1)[0]
    if c >= k:
        return Decision(True, sig, c, n, f"stable signature in {c}/{n} runs")
    return Decision(False, sig, c, n, f"modal signature only {c}/{n} (< k={k}); {len(counts)} distinct signatures")
