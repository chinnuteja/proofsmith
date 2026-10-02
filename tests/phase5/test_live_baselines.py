"""B0 and B1 on the six demo instances, then evaluate every bundle.

Dry-run verdicts are plumbing. They are not the evaluation.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

from proofsmith.agent.loop import Budget
from proofsmith.config import (
    EVAL_MODEL,
    MAX_STEPS,
    MAX_TOTAL_TOKENS,
    MAX_USD,
    MAX_WALL_S,
    REPO,
    RESULTS,
    WORK,
)
from proofsmith.datasets.schema import HiddenInstance, Instance
from proofsmith.eval.evaluator import evaluate
from proofsmith.ledger import LEDGER_PATH, Ledger
from proofsmith.llm import LLMClient
import proofsmith.ledger as ledger_mod
from proofsmith.systems import run_system

pytestmark = [pytest.mark.live, pytest.mark.timeout(21600)]

IDS = (
    "orderd-deadlock",
    "uaf-lru",
    "race-stats",
    "ub-notional",
    "rounding-ticks",
    "vague-perf",
)
SYSTEMS = ("b0", "b1", "proofsmith")
PHASE_CEILING = 0.75


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
    raise AssertionError(f"missing case {instance_id}")


def _bundle(instance_id: str, system: str) -> Path:
    if system == "proofsmith":
        return RESULTS / "verifiers" / instance_id / "bundle"
    return RESULTS / "dryrun" / instance_id / system


def _verdict_path(instance_id: str, system: str) -> Path:
    return RESULTS / "dryrun" / instance_id / f"{system}.json"


def _write(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8", newline="\n")


def test_dryrun_baselines_record_verdicts():
    before = Ledger(LEDGER_PATH).spent_usd()
    ledger_mod.MAX_USD = min(MAX_USD, before + PHASE_CEILING)
    rerun = os.environ.get("PROOFSMITH_RERUN") == "1"
    budget = Budget(MAX_STEPS, MAX_TOTAL_TOKENS, MAX_WALL_S)
    ledger = Ledger(LEDGER_PATH)

    for instance_id in IDS:
        instance, hidden = _case(instance_id)
        for system in ("b0", "b1"):
            bundle = _bundle(instance_id, system)
            have_bundle = (bundle / "verifier.json").is_file() and (bundle / "harness").is_dir()
            if have_bundle and not rerun:
                continue
            spent = ledger.spent_usd() - before
            if spent >= PHASE_CEILING:
                pytest.fail(f"phase ceiling ${PHASE_CEILING:.2f} reached at ${spent:.6f} before {instance_id} {system}")
            client = LLMClient(EVAL_MODEL, ledger, f"dryrun-{instance_id}-{system}")
            client.system_name = system
            run_system(system, instance, client, budget, bundle)
        for system in SYSTEMS:
            path = _verdict_path(instance_id, system)
            if path.is_file() and not rerun:
                continue
            bundle = _bundle(instance_id, system)
            verdict = evaluate(bundle, instance, hidden, WORK / "eval")
            payload = verdict.as_dict()
            verifier = bundle / "verifier.json"
            if verifier.is_file():
                meta = json.loads(verifier.read_text(encoding="utf-8"))
                payload["trajectory"] = meta.get("trajectory")
            _write(path, payload)

    missing = [
        f"{instance_id}/{system}"
        for instance_id in IDS
        for system in SYSTEMS
        if not _verdict_path(instance_id, system).is_file()
    ]
    assert not missing, missing
    for instance_id in IDS:
        for system in SYSTEMS:
            payload = json.loads(_verdict_path(instance_id, system).read_text(encoding="utf-8"))
            assert payload["schema"] == "proofsmith.verdict/1"
            assert payload["instance_id"] == instance_id
            assert payload["system"] == system
            assert "f2p" in payload
            assert "alignment" in payload
