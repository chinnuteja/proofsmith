"""Live deepseek-v4-pro verifier runs. Skips an instance whose bundle is already saved."""

from __future__ import annotations

import json
import os
import shutil
from pathlib import Path

import pytest

from proofsmith.agent.loop import Budget
from proofsmith.config import (
    EVAL_BUGGY_K,
    EVAL_MODEL,
    EVAL_N,
    MAX_STEPS,
    MAX_TOTAL_TOKENS,
    MAX_WALL_S,
    REPO,
    RESULTS,
    WORK,
)
from proofsmith.datasets.schema import Instance, apply_patch, materialize
from proofsmith.freeze import verify_bundle
from proofsmith.ledger import LEDGER_PATH, Ledger
from proofsmith.llm import LLMClient
from proofsmith.pipeline import make_verifier

pytestmark = pytest.mark.live

_PHASE_CEILING = 0.75
_MICROS = ("uaf-lru", "race-stats", "ub-notional", "rounding-ticks")
_ORDER = ("orderd-deadlock", "vague-perf", *_MICROS)


def _instance(case_dir: str) -> Instance:
    return Instance.model_validate_json((REPO / "cases" / case_dir / "instance.json").read_text(encoding="utf-8"))


def _saved(instance_id: str) -> Path:
    return RESULTS / "verifiers" / instance_id / "proofsmith.json"


def _publish(instance_id: str, bundle: Path) -> None:
    dest = RESULTS / "verifiers" / instance_id
    if dest.exists():
        shutil.rmtree(dest)
    shutil.copytree(bundle, dest / "bundle")
    shutil.copy2(bundle / "verifier.json", dest / "proofsmith.json")


def _load(instance_id: str) -> dict:
    return json.loads(_saved(instance_id).read_text(encoding="utf-8"))


def _ensure(instance_id: str, case_dir: str, ledger: Ledger, started: float) -> dict:
    if _saved(instance_id).is_file() and os.environ.get("PROOFSMITH_RERUN") != "1":
        print(f"{instance_id}: using saved bundle", flush=True)
        return _load(instance_id)
    phase_spent = ledger.spent_usd() - started
    if phase_spent >= _PHASE_CEILING:
        pytest.fail(f"phase ceiling ${_PHASE_CEILING:.2f} reached before {instance_id} (spent ${phase_spent:.6f})")
    out = WORK / "phase3" / instance_id / "bundle"
    client = LLMClient(EVAL_MODEL, ledger, f"phase3-{instance_id}")
    client.system_name = "proofsmith"
    result = make_verifier(
        _instance(case_dir),
        client,
        Budget(MAX_STEPS, MAX_TOTAL_TOKENS, MAX_WALL_S),
        out,
    )
    print(
        f"{instance_id}: status={result.status} oracle={result.oracle} "
        f"cost={result.cost_usd:.6f} reason={result.reason[:240]}",
        flush=True,
    )
    assert result.bundle_dir is not None
    _publish(instance_id, result.bundle_dir)
    return _load(instance_id)


def _fixed_fails(instance_id: str, case_dir: str) -> tuple[bool, int, int]:
    instance = _instance(case_dir)
    root = WORK / "phase3-verify" / instance_id
    fixed = materialize(instance, root / "fixed")
    patch = REPO / "cases" / case_dir / "hidden" / "fix.patch"
    apply_patch(fixed, patch)
    bundle = RESULTS / "verifiers" / instance_id / "bundle"
    verified = verify_bundle(bundle, fixed, instance.build, EVAL_N, root / "work")
    return verified.build_ok, verified.fails, verified.n


def test_live_pipeline():
    ledger = Ledger(LEDGER_PATH)
    started = ledger.spent_usd()
    print(f"ledger before phase3 live: ${started:.6f} ceiling ${_PHASE_CEILING:.2f}", flush=True)
    saved = {instance_id: _ensure(instance_id, instance_id if instance_id != "orderd-deadlock" else "orderd", ledger, started) for instance_id in _ORDER}

    orderd = saved["orderd-deadlock"]
    assert orderd["status"] == "accepted", orderd.get("abstain_reason")
    assert orderd["oracle"] == "tsan"
    signature = orderd["signature"] or ""
    assert signature.split("|", 1)[0] == "tsan:lock-order-inversion", signature
    assert "OrderBook::cancel" in signature or "OrderBook::risk_sweep" in signature, signature

    instance = _instance("orderd")
    for name, floor in (("scoped_cancel", None), ("consistent_order", None), ("timing_backoff", EVAL_BUGGY_K)):
        root = WORK / "phase3-verify" / "orderd" / name
        tree = materialize(instance, root / "tree")
        apply_patch(tree, REPO / "cases" / "orderd" / "variants" / f"{name}.patch")
        verified = verify_bundle(
            RESULTS / "verifiers" / "orderd-deadlock" / "bundle",
            tree,
            instance.build,
            EVAL_N,
            root / "work",
        )
        assert verified.build_ok, name
        print(f"orderd {name}: {verified.fails}/{verified.n}", flush=True)
        if floor is None:
            assert verified.fails == 0, name
        else:
            assert verified.fails >= floor, name

    vague = saved["vague-perf"]
    assert vague["status"] == "abstained", vague
    assert str(vague.get("abstain_reason") or "").startswith("NO VERIFIER:")

    good = []
    for instance_id in _MICROS:
        payload = saved[instance_id]
        if payload["status"] != "accepted":
            print(f"{instance_id}: not accepted ({payload.get('abstain_reason')})", flush=True)
            continue
        build_ok, fails, count = _fixed_fails(instance_id, instance_id)
        print(f"{instance_id}: fixed {fails}/{count} build_ok={build_ok}", flush=True)
        if build_ok and fails == 0:
            good.append(instance_id)
    assert len(good) >= 3, {"accepted_on_fixed": good, "all": {key: saved[key].get("status") for key in _MICROS}}
    after = ledger.spent_usd()
    print(f"ledger after phase3 live: ${after:.6f} phase_spent ${after - started:.6f}", flush=True)
    assert after - started <= _PHASE_CEILING + 1e-9
