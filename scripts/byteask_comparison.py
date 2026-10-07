"""Offline preparation and scoring for a five-case paired ByteAsk acceptance test.

No function in this module launches a model or creates a provider client. A real
run needs account access and free quota or an approved, enforceable usage limit.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import time

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from byteask_comparison_cases import CASE_IDS, write_cases
from proofsmith import config
from proofsmith.datasets.schema import BuildRecipe
from proofsmith.gate import _copy_source, check_patch, check_receipt, seal
from proofsmith.isolation import child_env, isolated_command
from proofsmith.oracles.builds import snapshot_sha256

ROOT = Path(__file__).resolve().parents[1]
RECIPE = BuildRecipe(system="cmake", test_command="ctest --output-on-failure")


def dump(path: Path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def digest(path: Path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def assets(directory: Path):
    if any(p.is_symlink() for p in directory.rglob("*")):
        raise ValueError("comparison assets must not contain symlinks")
    return {p.relative_to(directory).as_posix(): digest(p)
            for p in sorted(directory.rglob("*")) if p.is_file()}


def validate(directory: Path):
    protocol = json.loads((directory / "protocol.json").read_text())
    if protocol["case_ids"] != CASE_IDS or len(set(protocol["case_ids"])) != 5:
        raise ValueError("case selection changed")
    if protocol["asset_hashes"] != assets(directory / "cases"):
        raise ValueError("a case, control or judge changed after the freeze")
    for relative, expected in protocol["implementation_hashes"].items():
        if digest(ROOT / relative) != expected:
            raise ValueError(f"implementation changed: {relative}")
    for case_id in CASE_IDS:
        check_receipt(directory / "evidence" / case_id / "qualification")
    return protocol


def judge(repo: Path, judge_source: Path, out: Path):
    """Compile and run the independent evaluator with no network or home mount."""
    out.mkdir(parents=True, exist_ok=False)
    before = snapshot_sha256(repo)
    config.WORK.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="paired-judge-", dir=config.WORK) as name:
        work = Path(name)
        source = work / "source"
        _copy_source(repo, source)
        binary = work / "judge"
        commands = ["clang++", "-std=c++17", "-O0", "-g", "-I", str(source),
                    str(judge_source), str(source / "subject.cpp"), "-o", str(binary)]
        build = subprocess.run(isolated_command(commands, work, read=[judge_source.parent], write=[work]),
                               env=child_env(), capture_output=True, text=True, timeout=120)
        (out / "build.log").write_text(build.stdout + build.stderr)
        result = {"status": "UNRESOLVED", "source_sha256": before, "checks": None,
                  "failures": None, "build_exit_code": build.returncode}
        if build.returncode == 0:
            try:
                run = subprocess.run(isolated_command([str(binary)], work, write=[work]),
                                     env=child_env(), capture_output=True, text=True, timeout=30)
                (out / "run.log").write_text(run.stdout + run.stderr)
                measurement = json.loads(run.stdout)
                count, failures = measurement["checked"], measurement["failures"]
                if isinstance(count, int) and count > 0 and isinstance(failures, int) and 0 <= failures <= count:
                    result.update(checks=count, failures=failures, run_exit_code=run.returncode,
                                  status="CORRECT_ON_JUDGE" if failures == 0 and run.returncode == 0 else "INCORRECT")
            except (subprocess.TimeoutExpired, ValueError, KeyError, TypeError) as exc:
                result["reason"] = type(exc).__name__
        if snapshot_sha256(repo) != before or snapshot_sha256(source) != before:
            result.update(status="UNRESOLVED", reason="source changed during evaluation")
    dump(out / "result.json", result)
    return result


def smoke(repo: Path, out: Path):
    out.mkdir(parents=True, exist_ok=False)
    config.WORK.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="paired-smoke-", dir=config.WORK) as name:
        work = Path(name)
        source = work / "source"
        _copy_source(repo, source)
        binary = work / "smoke"
        cmd = ["clang++", "-std=c++17", "-O0", "-I", str(source),
               str(source / "smoke.cpp"), str(source / "subject.cpp"), "-o", str(binary)]
        build = subprocess.run(isolated_command(cmd, work, write=[work]),
                               env=child_env(), capture_output=True, text=True, timeout=120)
        (out / "build.log").write_text(build.stdout + build.stderr)
        run = None
        if build.returncode == 0:
            run = subprocess.run(isolated_command([str(binary)], work, write=[work]),
                                 env=child_env(), capture_output=True, text=True, timeout=30)
            (out / "run.log").write_text(run.stdout + run.stderr)
        return build.returncode == 0 and run is not None and run.returncode == 0


def prepare(directory: Path):
    directory.mkdir(parents=True, exist_ok=False)
    write_cases(directory / "cases")
    start = time.monotonic()
    controls = []
    for case_id in CASE_IDS:
        print(f"Preparing {case_id}", flush=True)
        case = directory / "cases" / case_id
        evidence = directory / "evidence" / case_id
        qualified = seal(case / "original", case / "supplied", RECIPE, "assertion", evidence / "qualification")
        if qualified["status"] != "VERIFIED":
            raise ValueError(f"check did not qualify: {case_id}: {qualified['reason']}")
        for variant in ("original", "fixed", "partial"):
            candidate = directory / "controls" / case_id / variant
            _copy_source(case / "original", candidate)
            if variant != "original":
                shutil.copyfile(case / "controls" / f"{variant}.cpp", candidate / "subject.cpp")
            ordinary_pass = smoke(candidate, evidence / variant / "smoke")
            truth = judge(candidate, case / "hidden/judge.cpp", evidence / variant / "judge")
            gate = check_patch(evidence / "qualification/bundle", case / "original", candidate,
                               RECIPE, evidence / variant / "gate", qualified["bundle_id"])
            check_receipt(evidence / variant / "gate")
            expected_judge = "CORRECT_ON_JUDGE" if variant == "fixed" else "INCORRECT"
            if not ordinary_pass or truth["status"] != expected_judge:
                raise ValueError(f"invalid control {case_id}/{variant}: smoke={ordinary_pass}, judge={truth}")
            if (variant == "fixed" and gate["status"] != "VERIFIED") or (variant != "fixed" and gate["status"] == "VERIFIED"):
                raise ValueError(f"unexpected gate result {case_id}/{variant}: {gate['status']}")
            controls.append({"case_id": case_id, "variant": variant, "origin": "authored_control",
                             "ordinary_smoke_pass": ordinary_pass, "judge_status": truth["status"],
                             "judge_checks": truth["checks"], "judge_failures": truth["failures"],
                             "gate_status": gate["status"], "baseline_failures": gate.get("baseline", {}).get("fails"),
                             "candidate_failures": gate.get("candidate", {}).get("fails"),
                             "receipt": (evidence / variant / "gate/receipt.json").relative_to(directory).as_posix()})
    tracked = list((ROOT / "proofsmith").rglob("*.py")) + [
        ROOT / "scripts/byteask_comparison.py", ROOT / "scripts/byteask_comparison_cases.py",
        ROOT / "proofsmith/runtime/proofsmith_check.h", ROOT / "docs/protocol.json"]
    protocol = {"schema": "proofsmith.byteask-paired/1", "id": "byteask-paired-v1",
                "case_ids": CASE_IDS, "case_kind": "fresh authored synthetic boundary cases",
                "comparison": "same candidate: ByteAsk claimed acceptance vs claimed acceptance AND frozen gate VERIFIED",
                "primary": "incorrect candidates accepted", "secondary": ["correct candidates accepted", "unresolved", "wall_s", "account_usage"],
                "model_runs": 5, "max_turns_per_case": 20, "max_wall_s_per_case": 600,
                "model": None, "provider": None, "max_additional_spend_usd": 0.0,
                "usage_policy": "existing free quota only; no purchase, upgrade, top-up or paid fallback",
                "gate_runs_per_side": 20,
                "decision": "continue only if incorrect acceptances decrease, correct acceptances do not decrease, and at least one correct candidate is accepted; otherwise stop or report no advantage",
                "generalization": "five cases cannot establish broad superiority; independent held-out confirmation is required",
                "asset_hashes": assets(directory / "cases"),
                "implementation_hashes": {p.relative_to(ROOT).as_posix(): digest(p) for p in tracked}}
    dump(directory / "protocol.json", protocol)
    summary = {"schema": "proofsmith.byteask-offline-controls/1", "model_calls": 0,
               "byteask_comparison_complete": False, "byteask_model_observations": 0,
               "claim": "offline synthetic control validation only; no ByteAsk win measured",
               "wall_s": time.monotonic() - start, "protocol_sha256": digest(directory / "protocol.json"),
               "controls": controls,
               "counts": {"controls": len(controls), "ordinary_smoke_pass": sum(c["ordinary_smoke_pass"] for c in controls),
                          "incorrect_controls_not_approved": sum(c["judge_status"] == "INCORRECT" and c["gate_status"] != "VERIFIED" for c in controls),
                          "correct_controls_approved": sum(c["judge_status"] == "CORRECT_ON_JUDGE" and c["gate_status"] == "VERIFIED" for c in controls)}}
    dump(directory / "offline-results.json", summary)
    dump(directory / "observations.pending.json", [
        {"case_id": case_id, "origin": "not_run", "candidate_path": None, "claimed_status": "UNRESOLVED",
         "wall_s": None, "account_usage": None} for case_id in CASE_IDS])
    validate(directory)
    print(json.dumps(summary["counts"], indent=2), flush=True)
    render(directory, summary)


def metrics(rows):
    seen = [r["case_id"] for r in rows]
    if len(set(seen)) != len(seen) or any(case_id not in CASE_IDS for case_id in seen):
        raise ValueError("duplicate or unselected case")
    complete = set(seen) == set(CASE_IDS) and all(r["origin"] == "byteask_model" for r in rows)
    valid = complete and all(r["judge_status"] in {"CORRECT_ON_JUDGE", "INCORRECT"} for r in rows)
    raw_bad = sum(r["byteask_accepted"] and r["judge_status"] == "INCORRECT" for r in rows)
    augmented_bad = sum(r["augmented_accepted"] and r["judge_status"] == "INCORRECT" for r in rows)
    raw_good = sum(r["byteask_accepted"] and r["judge_status"] == "CORRECT_ON_JUDGE" for r in rows)
    augmented_good = sum(r["augmented_accepted"] and r["judge_status"] == "CORRECT_ON_JUDGE" for r in rows)
    signal = valid and raw_bad > augmented_bad and augmented_good >= raw_good and augmented_good > 0
    return {"complete": complete, "valid_for_pilot_claim": valid, "observations": len(rows),
            "byteask_incorrect_accepted": raw_bad, "augmented_incorrect_accepted": augmented_bad,
            "byteask_correct_accepted": raw_good, "augmented_correct_accepted": augmented_good,
            "positive_pilot_signal": signal,
            "claim": "positive signal on five synthetic cases; held-out confirmation required" if signal else
                     "no demonstrated advantage" if valid else "comparison incomplete or invalid; no win claim"}


def score(directory: Path, observations: Path, out: Path):
    validate(directory)
    items = json.loads(observations.read_text())
    if not isinstance(items, list) or len(items) > 5:
        raise ValueError("observations must be a list with at most five selected cases")
    ids = [item["case_id"] for item in items]
    if len(ids) != len(set(ids)) or any(x not in CASE_IDS for x in ids):
        raise ValueError("duplicate or unselected case")
    if any(item["origin"] != "byteask_model" for item in items):
        raise ValueError("scripted providers and authored controls cannot enter model scores")
    # A caller label alone is not model evidence. Require a retained transcript
    # and consistent pinned execution settings before touching candidate code.
    for item in items:
        trace = Path(item["transcript_path"])
        if digest(trace) != item["transcript_sha256"]:
            raise ValueError("ByteAsk transcript changed")
        if not item["model"] or not item["provider"] or any(
                marker in item["provider"].lower() for marker in ("fixture", "localhost", "scripted")):
            raise ValueError("pin a real model and provider")
        if item["protocol_sha256"] != digest(directory / "protocol.json"):
            raise ValueError("observation belongs to a different protocol")
    if len({(item["model"], item["provider"]) for item in items}) > 1:
        raise ValueError("all cases must use the same pinned model and provider")
    out.mkdir(parents=True, exist_ok=False)
    rows = []
    for item in items:
        case_id = item["case_id"]
        candidate = Path(item["candidate_path"]).resolve()
        case = directory / "cases" / case_id
        evidence = directory / "evidence" / case_id
        sealed = json.loads((evidence / "qualification/receipt.json").read_text())
        truth = judge(candidate, case / "hidden/judge.cpp", out / case_id / "judge")
        gate_started = time.monotonic()
        gate = check_patch(evidence / "qualification/bundle", case / "original", candidate,
                           RECIPE, out / case_id / "gate", sealed["bundle_id"])
        if item["claimed_status"] not in {"ACCEPTED", "UNRESOLVED"}:
            raise ValueError("claimed_status must be ACCEPTED or UNRESOLVED")
        accepted = item["claimed_status"] == "ACCEPTED"
        rows.append({**item, "judge_status": truth["status"], "judge_checks": truth["checks"],
                     "gate_status": gate["status"], "gate_wall_s": time.monotonic() - gate_started,
                     "byteask_accepted": accepted,
                     "augmented_accepted": accepted and gate["status"] == "VERIFIED"})
    result = {"schema": "proofsmith.byteask-paired-results/1", "rows": rows, "metrics": metrics(rows),
              "protocol_sha256": digest(directory / "protocol.json")}
    dump(out / "results.json", result)
    print(json.dumps(result["metrics"], indent=2))


def render(directory: Path, summary):
    from html import escape
    rows = "".join(f'<tr><td>{escape(r["case_id"])}</td><td>{r["variant"]}</td><td>PASS</td>'
                   f'<td>{r["judge_status"]} ({r["judge_failures"]}/{r["judge_checks"]})</td>'
                   f'<td><a href="{r["receipt"][:-12]}index.html">{r["gate_status"]}</a></td></tr>'
                   for r in summary["controls"])
    html = f'''<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Proofsmith: ByteAsk comparison preparation</title><style>body{{font:16px system-ui;background:#101820;color:#e5edf5;margin:0;padding:32px;max-width:1000px}}h1{{font-size:30px}}p{{line-height:1.6}}a{{color:#8ecbff}}.table{{overflow:auto}}table{{border-collapse:collapse;width:100%;font-size:14px}}th,td{{padding:12px;text-align:left;border-bottom:1px solid #344453}}.badge{{padding:12px;border:1px solid #ffd280;color:#ffd280}}code{{overflow-wrap:anywhere}}</style>
<h1>Five cases prepared. ByteAsk results pending.</h1><p class="badge">OFFLINE CONTROLS — zero model requests. No ByteAsk win measured.</p>
<p>The frozen supplied check gates the same candidate ByteAsk produces. The independent judge checks additional inputs. These fifteen authored controls validate the test setup and are excluded from model scores.</p>
<div class="table"><table><thead><tr><th>Case</th><th>Control</th><th>Ordinary smoke</th><th>Independent judge</th><th>Frozen gate</th></tr></thead><tbody>{rows}</tbody></table></div>
<p>Real model observations: <strong>0 / 5</strong>. Both available ByteAsk profiles are signed out. The next step uses existing free quota with zero additional spending; no purchase, upgrade or paid fallback. The available model/provider must be pinned before running.</p>
<p>A positive pilot requires fewer incorrect candidates accepted without losing correct acceptances, and at least one correct candidate accepted. Rejecting everything is insufficient. An all-correct baseline means no advantage demonstrated. Five synthetic cases do not establish general superiority.</p>
<p>Protocol SHA-256: <code>{summary["protocol_sha256"]}</code></p><p><a href="protocol.json">Protocol</a> · <a href="offline-results.json">Offline measurements</a></p></html>'''
    (directory / "index.html").write_text(html, encoding="utf-8")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    prepare_parser = sub.add_parser("prepare")
    prepare_parser.add_argument("--out", type=Path, required=True)
    validate_parser = sub.add_parser("validate")
    validate_parser.add_argument("--experiment", type=Path, required=True)
    score_parser = sub.add_parser("score")
    score_parser.add_argument("--experiment", type=Path, required=True)
    score_parser.add_argument("--observations", type=Path, required=True)
    score_parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    os.environ["DEEPSEEK_API_KEY"] = ""
    if args.command == "prepare":
        prepare(args.out.resolve())
    elif args.command == "validate":
        protocol = validate(args.experiment.resolve())
        print(json.dumps({"valid": True, "id": protocol["id"], "model_calls": 0}))
    else:
        score(args.experiment.resolve(), args.observations, args.out.resolve())


if __name__ == "__main__":
    main()
