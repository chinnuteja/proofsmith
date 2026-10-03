"""Offline reproduction of frozen artifacts, kept separate from new experiments."""
from __future__ import annotations

import json
from pathlib import Path

from proofsmith import config
from proofsmith.datasets.schema import HiddenInstance, Instance
from proofsmith.eval.evaluator import evaluate
from proofsmith.eval.runner import atomic_json
from proofsmith.freeze import load_bundle

OUTCOME_FIELDS = ("instance_id", "system", "track", "bundle_status", "build_ok_buggy",
                  "build_ok_fixed", "buggy_fails", "fixed_fails", "n", "f2p")


def outcome(value: dict) -> dict:
    return {**{k: value.get(k) for k in OUTCOME_FIELDS},
            "alignment": {k: value.get("alignment", {}).get(k) for k in ("strict", "relaxed", "unknown")}}


def find_case(name: str) -> tuple[Instance, HiddenInstance]:
    for path in sorted((config.REPO / "cases").glob("*/instance.json")):
        instance = Instance.model_validate_json(path.read_text())
        if instance.id == name:
            return instance, HiddenInstance.model_validate_json((path.parent / "hidden/hidden.json").read_text())
    from proofsmith.eval.runner import load_case

    for track in ("A", "B"):
        if (config.REPO / "data" / f"track{track}" / "instances" / f"{name}.json").is_file():
            return load_case(track, name)
    raise ValueError(f"unknown instance {name}")


def expected_path(bundle: Path, meta: dict) -> Path:
    if bundle.name == "bundle":
        # The sibling proofsmith.json is runtime metadata, not a hidden
        # evaluator verdict. The plumbing run stores its verdict separately.
        return config.RESULTS / "dryrun" / meta["instance_id"] / f"{meta['system']}.json"
    return bundle.with_suffix(".json")


def replay_all(*, check: bool = False, only: Path | None = None) -> dict:
    roots = ("verifiers", "eval", "dryrun")
    bundles = [only.resolve()] if only else sorted(
        p.parent for name in roots for p in (config.RESULTS / name).rglob("verifier.json")
        if not p.parent.name.endswith(".pending"))
    records = []
    for bundle in bundles:
        try:
            meta = load_bundle(bundle)
            instance, hidden = find_case(meta["instance_id"])
            value = evaluate(bundle, instance, hidden, config.WORK / "replay").as_dict()
            stored = expected_path(bundle, meta)
            previous = json.loads(stored.read_text()) if stored.is_file() else None
            matches = previous is not None and outcome(previous) == outcome(value)
            rel = bundle.resolve().relative_to(config.REPO.resolve()).as_posix()
            path = config.RESULTS / "replay" / rel.removeprefix("results/") / "verdict.json"
            atomic_json(path, value)
            records.append({"bundle": rel, "stored": stored.relative_to(config.REPO).as_posix(),
                "matches": matches, "recomputed": outcome(value), "previous": outcome(previous) if previous else None})
            print(f"replay {meta['instance_id']}/{meta['system']}: f2p={value['f2p']} matches={matches}", flush=True)
        except Exception as exc:
            records.append({"bundle": str(bundle), "matches": False, "error": f"{type(exc).__name__}: {exc}"})
    payload = {"schema": "proofsmith.replay/1", "check": check,
               "matches": bool(records) and all(r["matches"] for r in records), "records": records}
    atomic_json(config.RESULTS / "replay_summary.json", payload)
    return payload
