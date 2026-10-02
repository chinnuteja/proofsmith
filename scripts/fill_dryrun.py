"""Fill remaining dry-run verdicts without more API calls.

Live B0/B1 on later micros were stopped so remaining credit can go to Track B.
Proofsmith bundles already exist from Phase 3. Evaluate those locally.
"""

from __future__ import annotations

import json
from pathlib import Path

from proofsmith.config import REPO, RESULTS, WORK
from proofsmith.datasets.schema import HiddenInstance, Instance
from proofsmith.eval.evaluator import evaluate

IDS = (
    "orderd-deadlock",
    "uaf-lru",
    "race-stats",
    "ub-notional",
    "rounding-ticks",
    "vague-perf",
)
SKIP = (
    ("race-stats", "b1"),
    ("ub-notional", "b0"),
    ("ub-notional", "b1"),
    ("rounding-ticks", "b0"),
    ("rounding-ticks", "b1"),
    ("vague-perf", "b0"),
    ("vague-perf", "b1"),
)
REASON = "not run: remaining DeepSeek credit reserved for Track B"


def _case(instance_id: str) -> tuple[Instance, HiddenInstance]:
    for path in sorted((REPO / "cases").glob("*/instance.json")):
        payload = json.loads(path.read_text(encoding="utf-8"))
        if payload.get("id") != instance_id:
            continue
        hidden = path.parent / "hidden" / "hidden.json"
        return (
            Instance.model_validate(payload),
            HiddenInstance.model_validate_json(hidden.read_text(encoding="utf-8")),
        )
    raise SystemExit(f"missing case {instance_id}")


def _write(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8", newline="\n")


def _skipped(instance: Instance, system: str) -> dict:
    return {
        "schema": "proofsmith.verdict/1",
        "instance_id": instance.id,
        "system": system,
        "track": instance.track,
        "bundle_status": "gave_up",
        "build_ok_buggy": False,
        "build_ok_fixed": False,
        "buggy_fails": 0,
        "fixed_fails": 0,
        "n": 0,
        "f2p": False,
        "alignment": {"strict": False, "relaxed": False, "unknown": False, "hits": [], "changed": []},
        "oracle": None,
        "evidence_kinds": {},
        "cost_usd": 0.0,
        "wall_s": 0.0,
        "error": REASON,
        "trajectory": "",
    }


def main() -> None:
    for instance_id, system in SKIP:
        path = RESULTS / "dryrun" / instance_id / f"{system}.json"
        if path.is_file():
            continue
        instance, _hidden = _case(instance_id)
        _write(path, _skipped(instance, system))
        print(f"skipped {instance_id} {system}")

    evaluate_pairs = [
        ("race-stats", "b0", RESULTS / "dryrun" / "race-stats" / "b0"),
    ]
    for instance_id in IDS:
        bundle = RESULTS / "verifiers" / instance_id / "bundle"
        verdict = RESULTS / "dryrun" / instance_id / "proofsmith.json"
        if bundle.is_dir() and not verdict.is_file():
            evaluate_pairs.append((instance_id, "proofsmith", bundle))

    for instance_id, system, bundle in evaluate_pairs:
        dest = RESULTS / "dryrun" / instance_id / f"{system}.json"
        if dest.is_file() and system != "b0":
            continue
        if system == "b0" and dest.is_file():
            continue
        instance, hidden = _case(instance_id)
        verdict = evaluate(bundle, instance, hidden, WORK / "eval" / f"dry-{instance_id}-{system}")
        payload = verdict.as_dict()
        verifier = bundle / "verifier.json"
        if verifier.is_file():
            meta = json.loads(verifier.read_text(encoding="utf-8"))
            payload["trajectory"] = meta.get("trajectory") or ""
        _write(dest, payload)
        print(f"evaluated {instance_id} {system} f2p={payload['f2p']} err={payload.get('error')}")


if __name__ == "__main__":
    main()
