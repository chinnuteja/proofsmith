"""Freeze a population and execution order before spending on an experiment."""
from __future__ import annotations

import hashlib
import json
import random
from datetime import datetime, timezone
from pathlib import Path

from proofsmith import config

PROTOCOL_PATH = config.REPO / "docs/protocol.json"


def fingerprint(payload: dict) -> str:
    return hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def freeze_protocol(path: Path = PROTOCOL_PATH) -> dict:
    if path.exists():
        return json.loads(path.read_text())
    excluded = set()
    exclusion_file = config.REPO / "data/trackB/EXCLUDED.md"
    if exclusion_file.exists():
        excluded = {line[3:].strip() for line in exclusion_file.read_text().splitlines() if line.startswith("## ")}
    tracks = {
        track: sorted(p.stem for p in (config.REPO / "data" / f"track{track}" / "instances").glob("*.json") if p.stem not in excluded)
        for track in ("B", "A")
    }
    rng = random.Random(20261001)
    order = []
    for track, ids in tracks.items():
        for name in ids:
            systems = ["b0", "b1", "proofsmith"]
            rng.shuffle(systems)
            order.extend({"track": track, "instance_id": name, "system": system} for system in systems)
    files = sorted((config.REPO / "proofsmith").rglob("*.py")) + sorted((config.REPO / "proofsmith/prompts").glob("*.md"))
    files += sorted((config.REPO / "proofsmith/runtime").glob("*.h"))
    for track in tracks:
        files += sorted((config.REPO / "data" / f"track{track}" / "instances").glob("*.json"))
        files += sorted((config.REPO / "data" / f"track{track}" / "hidden").glob("*"))
    files += sorted((config.REPO / "scripts").glob("*build*.sh"))
    files += [config.REPO / "pyproject.toml", config.REPO / "config/pricing.json",
              config.REPO / "data/trackB/EXCLUDED.md"]
    hashes = {p.relative_to(config.REPO).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest() for p in files if p.is_file()}
    payload = {"schema": "proofsmith.protocol/1", "id": "v1", "created_at": datetime.now(timezone.utc).isoformat(),
        "model": config.EVAL_MODEL, "temperature": 0, "seed": 20261001,
        "budget": {"max_steps": config.MAX_STEPS, "max_total_tokens": config.MAX_TOTAL_TOKENS, "max_wall_s": config.MAX_WALL_S},
        "constants": {name: getattr(config, name) for name in ("RUNTIME_N", "RUNTIME_K", "EVAL_N", "EVAL_BUGGY_K", "EVAL_FIXED_MAX_FAILS", "RUN_TIMEOUT_S")},
        "tracks": tracks, "excluded": sorted(excluded), "order": order,
        "pilot": {track: ids[:2] for track, ids in tracks.items()}, "files": hashes}
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    write_protocol_document(payload, path.with_suffix(".md"))
    return payload


def validate_protocol(payload: dict) -> None:
    for rel, digest in payload["files"].items():
        p = config.REPO / rel
        if not p.is_file() or hashlib.sha256(p.read_bytes()).hexdigest() != digest:
            raise RuntimeError(f"protocol input changed: {rel}; freeze a new protocol before running")
    if payload["model"] != config.EVAL_MODEL:
        raise RuntimeError("protocol model differs from configuration")
    for name, value in payload["constants"].items():
        if getattr(config, name) != value:
            raise RuntimeError(f"protocol constant differs from configuration: {name}")
    expected = {(track, name, system) for track, ids in payload["tracks"].items()
                for name in ids for system in ("b0", "b1", "proofsmith")}
    actual = [(p["track"], p["instance_id"], p["system"]) for p in payload["order"]]
    if len(actual) != len(expected) or set(actual) != expected:
        raise RuntimeError("protocol order must contain every pair exactly once")


def write_protocol_document(payload: dict, path: Path) -> None:
    text = f"""# Frozen evaluation protocol

Protocol ID: `{payload['id']}`. SHA-256: `{fingerprint(payload)}`.
The complete population, execution order, constants, budgets, source hashes and exclusions are in [{path.with_suffix('.json').name}]({path.with_suffix('.json').name}).
Frozen at `{payload['created_at']}` before new observations. Historical exploratory samples are retained separately and cannot enter this protocol's metrics.

Model: `{payload['model']}`, temperature `{payload['temperature']}`, randomized system order with seed `{payload['seed']}`.
Shared budget: `{payload['budget']['max_steps']}` steps, `{payload['budget']['max_total_tokens']}` total prompt plus completion tokens, `{payload['budget']['max_wall_s']}` seconds. Classifier calls count toward Proofsmith's budget. All systems receive the same tools, model, and budget.

Runtime acceptance requires stable eligible evidence in {payload['constants']['RUNTIME_K']} of {payload['constants']['RUNTIME_N']} runs.
Evaluation raw F→P requires successful builds on both trees, at least {payload['constants']['EVAL_BUGGY_K']} buggy failures in {payload['constants']['EVAL_N']} runs and {payload['constants']['EVAL_FIXED_MAX_FAILS']} fixed failures. Timeout per run: {payload['constants']['RUN_TIMEOUT_S']} seconds.
Alignment strict means a failure frame or executed coverage region overlaps a function actually changed by the fix; relaxed means a changed source file is hit. Diff context alone does not change a function. Unavailable coverage is unknown. Alignment does not alter raw F→P.

One generation attempt per pair. Interrupted attempts remain auditable and are not silently regenerated. Per-pair infrastructure errors are stored. An explicit infrastructure retry requires a separate logged decision. Existing verdicts are immutable. Only the evaluator sees the hidden fixed code.

## Metrics and kill criteria

Report raw, aligned strict and aligned relaxed F→P counts and percentages with Wilson 95% intervals; unknown alignment; successful oracles; median cost and wall time; and fixed-tree flake rate (1 ≤ fixed failures < evaluation run count, divided by submitted or accepted bundles).
Abstention precision is Proofsmith abstentions where B1 is also not F→P divided by paired Proofsmith abstentions. Missing B1 observations do not count as correct abstentions.
Paired exact two-sided McNemar compares aligned strict success against B1, with discordant counts b and c and `min(1, 2 * sum(comb(b+c, i) for i in range(min(b,c)+1)) / 2**(b+c))`.

- Track B verdict `PASS` if `aligned_strict_pct(proofsmith) − aligned_strict_pct(b1) ≥ 20` points, else `KILL_OR_RETHINK`.
- Track A verdict `OK` if `raw_pct(proofsmith) ≥ raw_pct(b1) − 5`, else `RESTRICT_TO_LIFETIME_CONCURRENCY`.

An incomplete experiment reports `INCOMPLETE`. Unresolved alignment reports `ALIGNMENT_UNRESOLVED`; it cannot support a success claim. No missing observation is filled with a fabricated failure or success.

## Pilot and approval

Pilot: two Track B and two Track A instances, all three systems. `results/pilot_cost.json` records per-system mean and maximum cost and wall time, with a full-run projection using a 1.3 safety multiplier. Stop after the pilot. A full run requires human budget approval recorded in `docs/phase-logs/phase-6.md` and `docs/evaluation-approval.json`, tied to this protocol's SHA-256. Current preparation grants no new spending approval.

## Populations

"""
    for track, names in payload["tracks"].items():
        text += f"Track {track}: " + ", ".join(f"`{name}`" for name in names) + ".\n\n"
        text += f"Pilot {track}: " + ", ".join(f"`{name}`" for name in payload["pilot"][track]) + ".\n\n"
    text += "Excluded: " + ", ".join(f"`{name}`" for name in payload["excluded"]) + ". See `data/trackB/EXCLUDED.md`.\n\n## Execution order\n\n"
    text += "\n".join(f"{i}. {p['track']}/{p['instance_id']}/{p['system']}" for i, p in enumerate(payload["order"], 1)) + "\n"
    path.write_text(text, encoding="utf-8")
