"""Resumable protocol-bound evaluation, pilot costing, and offline replay."""
from __future__ import annotations

import json
import os
import statistics
import uuid
from datetime import datetime, timezone
from pathlib import Path

from proofsmith import config
from proofsmith.agent.loop import Budget
from proofsmith.datasets.schema import HiddenInstance, Instance
from proofsmith.eval.evaluator import evaluate
from proofsmith.eval.metrics import SYSTEMS, summarize
from proofsmith.eval.protocol import PROTOCOL_PATH, fingerprint, validate_protocol
from proofsmith.freeze import load_bundle
from proofsmith.ledger import BudgetExceeded, LEDGER_PATH, Ledger
from proofsmith.llm import LLMClient
from proofsmith.systems import run_system


def atomic_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + f".{uuid.uuid4().hex}.tmp")
    try:
        temporary.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def load_case(track: str, name: str) -> tuple[Instance, HiddenInstance]:
    root = config.REPO / "data" / f"track{track}"
    return (Instance.model_validate_json((root / "instances" / f"{name}.json").read_text()),
            HiddenInstance.model_validate_json((root / "hidden" / f"{name}.json").read_text()))


def result_root(protocol: dict) -> Path:
    # Legacy exploratory samples are retained; they cannot silently enter a new experiment.
    return config.RESULTS / "eval" / protocol["id"]


def _error(pair: dict, error: str, cost: float) -> dict:
    return {"schema": "proofsmith.verdict/1", **pair, "bundle_status": "error",
        "build_ok_buggy": False, "build_ok_fixed": False, "buggy_fails": 0, "fixed_fails": 0,
        "n": 0, "f2p": False, "alignment": {"strict": False, "relaxed": False, "unknown": True, "hits": []},
        "oracle": None, "cost_usd": cost, "wall_s": 0, "evidence_kinds": {}, "error": error}


def run_eval(track: str = "all", systems: list[str] | None = None,
             instance_ids: list[str] | None = None, resume: bool = True, *, pilot: bool = False,
             protocol_path: Path = PROTOCOL_PATH, client_factory=LLMClient) -> dict:
    protocol = json.loads(protocol_path.read_text())
    validate_protocol(protocol)
    digest = fingerprint(protocol)
    if not pilot:
        approval = config.REPO / "docs/evaluation-approval.json"
        if not approval.is_file() or json.loads(approval.read_text()).get("protocol_sha256") != digest:
            raise RuntimeError("full evaluation requires a human budget approval for this protocol after the pilot")
        pilot_path = config.RESULTS / 'pilot_cost.json'
        audit_path = config.RESULTS / 'pilot_budget_audit.json'
        if not pilot_path.is_file() or not audit_path.is_file():
            raise RuntimeError('full evaluation requires a completed and budget-audited pilot for this protocol')
        pilot_record, audit = json.loads(pilot_path.read_text()), json.loads(audit_path.read_text())
        if not pilot_record.get('complete') or pilot_record.get('protocol_sha256') != digest or audit.get('protocol_sha256') != digest:
            raise RuntimeError('pilot or budget audit does not match the approved protocol')
        expected_audit = sum(map(len, protocol['pilot'].values())) * len(SYSTEMS)
        if audit.get('violations') or audit.get('observed_bundles') != expected_audit or audit.get('expected_bundles') != expected_audit:
            raise RuntimeError('pilot budget violations or incomplete audit block the full experiment')
    selected = set(systems or SYSTEMS)
    if not selected.issubset(SYSTEMS):
        raise ValueError("unknown system")
    ledger = Ledger(LEDGER_PATH)
    root = result_root(protocol)
    for pair in protocol["order"]:
        if track != "all" and pair["track"] != track or pair["system"] not in selected:
            continue
        if instance_ids is not None and pair["instance_id"] not in instance_ids:
            continue
        if pilot and pair["instance_id"] not in protocol["pilot"][pair["track"]]:
            continue
        dest = root / pair["track"] / pair["instance_id"] / f"{pair['system']}.json"
        if dest.exists():
            stored = json.loads(dest.read_text())
            if stored.get("protocol_sha256") != digest:
                raise RuntimeError(f"result protocol mismatch: {dest}")
            if resume:
                continue
            raise RuntimeError("existing observations are immutable; use a new protocol for repeats")
        instance, hidden = load_case(pair["track"], pair["instance_id"])
        bundle = dest.parent / pair["system"]
        temporary = bundle.with_name(bundle.name + ".pending")
        attempt = dest.with_suffix(".attempt.json")
        before = ledger.spent_usd()
        try:
            ledger.ensure_budget()
            if not (bundle / "verifier.json").is_file():
                if not (temporary / "verifier.json").is_file():
                    if attempt.exists():
                        raise RuntimeError("generation was interrupted; the single attempt is recorded as an error and will not be repeated")
                    client = client_factory(protocol["model"], ledger, f"{protocol['id']}-{pair['instance_id']}-{pair['system']}")
                    client.system_name = pair["system"]
                    atomic_json(attempt, {**pair, "protocol_sha256": digest,
                        "started_at": datetime.now(timezone.utc).isoformat(), "spend_before": before})
                    run_system(pair["system"], instance, client, Budget(**protocol["budget"]), temporary)
                meta = load_bundle(temporary)
                meta["protocol_sha256"] = digest
                atomic_json(temporary / "verifier.json", meta)
                os.replace(temporary, bundle)
            meta = load_bundle(bundle)
            if meta.get("protocol_sha256") != digest:
                raise RuntimeError("bundle protocol mismatch")
            value = evaluate(bundle, instance, hidden, config.WORK / "eval" / protocol["id"]).as_dict()
            value["trajectory"] = meta.get("trajectory")
            value["variant"] = meta.get("variant")
            value["mentions_fix"] = instance.issue.mentions_fix
        except BudgetExceeded as exc:
            # An unstarted pair is missing, not a zero-cost failed observation.
            if attempt.exists():
                value = _error(pair, str(exc), ledger.spent_usd() - before)
                value["protocol_sha256"] = digest
                atomic_json(dest, value)
            write_summary(protocol)
            if pilot:
                atomic_json(config.RESULTS / "pilot_cost.json", pilot_cost(protocol))
            raise
        except Exception as exc:
            original_spend = json.loads(attempt.read_text())["spend_before"] if attempt.exists() else before
            value = _error(pair, f"{type(exc).__name__}: {exc}", ledger.spent_usd() - original_spend)
        value["protocol_sha256"] = digest
        atomic_json(dest, value)
        print(f"{pair['track']}/{pair['instance_id']}/{pair['system']}: {value['bundle_status']} f2p={value['f2p']}", flush=True)
        if "BudgetExceeded" in str(value.get("error")):
            write_summary(protocol)
            raise BudgetExceeded(value["error"])
    summary = write_summary(protocol)
    if pilot:
        atomic_json(config.RESULTS / "pilot_cost.json", pilot_cost(protocol))
    return summary


def read_rows(protocol: dict) -> list[dict]:
    root = result_root(protocol)
    digest = fingerprint(protocol)
    rows = []
    for pair in protocol["order"]:
        path = root / pair["track"] / pair["instance_id"] / f"{pair['system']}.json"
        if path.is_file():
            row = json.loads(path.read_text())
            if row.get("protocol_sha256") != digest:
                raise RuntimeError(f"result protocol mismatch: {path}")
            rows.append(row)
    return rows


def write_summary(protocol: dict) -> dict:
    value = summarize(read_rows(protocol), protocol["tracks"])
    value.update({"protocol_sha256": fingerprint(protocol), "protocol_id": protocol["id"],
                  "generated_at": datetime.now(timezone.utc).isoformat()})
    atomic_json(config.RESULTS / "summary.json", value)
    return value


def pilot_cost(protocol: dict) -> dict:
    rows = [r for r in read_rows(protocol) if r["instance_id"] in protocol["pilot"][r["track"]]]
    systems = {}
    projection = 0.0
    complete = True
    for system in SYSTEMS:
        sample = [r for r in rows if r["system"] == system]
        expected = sum(len(v) for v in protocol["pilot"].values())
        complete = complete and len(sample) == expected
        count = sum(len(v) for v in protocol["tracks"].values())
        mean = statistics.mean(r["cost_usd"] for r in sample) if sample else None
        systems[system] = {"completed": len(sample), "expected": expected, "mean_cost_usd": mean,
            "max_cost_usd": max((r["cost_usd"] for r in sample), default=None),
            "mean_wall_s": statistics.mean(r["wall_s"] for r in sample) if sample else None}
        systems[system]["max_wall_s"] = max((r["wall_s"] for r in sample), default=None)
        if mean is not None:
            projection += mean * (count - len(sample)) * 1.3
    spent = Ledger(LEDGER_PATH).spent_usd()
    return {"schema": "proofsmith.pilot/1", "complete": complete, "protocol_sha256": fingerprint(protocol),
        "systems": systems, "projected_remaining_usd": projection if complete else None,
        "recorded_spend_usd": spent, "remaining_cap_usd": max(0, config.MAX_USD - spent), "safety_multiplier": 1.3}
