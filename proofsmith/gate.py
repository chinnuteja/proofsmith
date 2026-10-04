"""Offline, source-preserving qualification and patch verification with portable evidence."""
from __future__ import annotations

import hashlib
import json
import math
import shutil
import tempfile
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

from proofsmith import config
from proofsmith.datasets.schema import BuildRecipe
from proofsmith.freeze import TamperError, _harness_files, freeze, load_bundle, verify_bundle
from proofsmith.oracles.acceptance import ELIGIBLE, decide
from proofsmith.oracles.builds import snapshot_sha256

EXIT_CODES = {"VERIFIED": 0, "REJECTED": 1, "INCONCLUSIVE": 2}
LIMIT = "Evidence covers this frozen check and these source snapshots; it does not prove the patch correct for all inputs."


def _json(path: Path, value: dict) -> None:
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def bundle_id(bundle: Path) -> str:
    """Identity includes metadata as well as every validated harness byte."""
    meta = load_bundle(bundle)
    if (Path(bundle) / "verifier.json").is_symlink():
        raise TamperError("verifier metadata must not be a symlink")
    return hashlib.sha256(json.dumps(meta, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def _copy_source(source: Path, dest: Path) -> str:
    source = source.resolve()
    if not source.is_dir():
        raise ValueError("source must be an existing directory")
    # Never dereference source links into files outside the supplied source snapshot.
    for path in source.rglob("*"):
        rel = path.relative_to(source)
        if ".git" in rel.parts or "proofsmith_harness" in rel.parts:
            continue
        if path.is_symlink():
            raise ValueError(f"source symlinks are unsupported: {rel}")
    before = snapshot_sha256(source)
    shutil.copytree(source, dest, ignore=shutil.ignore_patterns(".git", "proofsmith_harness"))
    if snapshot_sha256(source) != before or snapshot_sha256(dest) != before:
        raise ValueError("source changed during snapshot; retry from a stable checkout")
    return before


def _output(out: Path, inputs: list[Path]) -> Path:
    out = out.resolve()
    for path in inputs:
        path = path.resolve()
        if out.is_relative_to(path) or path.is_relative_to(out):
            raise ValueError("output must be separate from source and bundle directories")
    out.mkdir(parents=True, exist_ok=False)
    return out


def _eligible(run, oracle: str, signature: str) -> bool:
    evidence = run.evidence
    return (not run.timed_out and run.exit_code != 0 and
            evidence.kind.startswith(ELIGIBLE[oracle]) and
            (evidence.kind == "assert" or bool(evidence.app_frames)) and
            evidence.signature == signature)


def _failed(run) -> bool:
    return run.timed_out or run.exit_code != 0


def _unchanged(tree: Path, source_id: str, bundle: Path) -> bool:
    return (snapshot_sha256(tree) == source_id and
            _harness_files(tree / "proofsmith_harness") == load_bundle(bundle)["files"])


def _record(result, work: Path, out: Path, side: str, oracle: str, signature: str) -> dict:
    evidence_dir = out / "evidence" / side
    evidence_dir.mkdir(parents=True)
    rows = []
    # Package actual run output and compiler diagnostics, including build failures.
    for path in sorted(work.rglob("*.log")):
        rel = path.relative_to(work)
        target = evidence_dir / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(path, target)
    for run in result.runs:
        log = Path(run.output_path)
        relative = (evidence_dir / log.relative_to(work)).relative_to(out).as_posix()
        rows.append({"index": run.index, "exit_code": run.exit_code, "timed_out": run.timed_out,
                     "duration_s": run.duration_s, "kind": run.evidence.kind,
                     "signature": run.evidence.signature, "matches_target": _eligible(run, oracle, signature),
                     "log": relative,
                     "application_frames": [{"function": f.function, "file": f.file, "line": f.line}
                                            for f in run.evidence.app_frames]})
    return {"build_ok": result.build_ok, "requested_runs": result.n, "completed_runs": len(rows),
            "fails": result.fails, "target_failures": sum(r["matches_target"] for r in rows),
            "unexpected_failures": sum(_failed(r) and not _eligible(r, oracle, signature) for r in result.runs),
            "evidence_kinds": dict(Counter(r.evidence.kind for r in result.runs)), "runs": rows}


def _finish(out: Path, receipt: dict) -> dict:
    receipt["exit_code"] = EXIT_CODES[receipt["status"]]
    receipt["limitation"] = LIMIT
    _json(out / "receipt.json", receipt)
    from proofsmith.report.gate import render_receipt
    render_receipt(out, receipt)
    files = {p.relative_to(out).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
             for p in sorted(out.rglob("*")) if p.is_file() and p != out / "manifest.json"}
    _json(out / "manifest.json", {"schema": "proofsmith.evidence-manifest/1", "files": files})
    return receipt


def seal(repo: Path, harness: Path, recipe: BuildRecipe, oracle: str, out: Path) -> dict:
    """Qualify a supplied check against the original code; no model call is made."""
    if oracle not in ELIGIBLE:
        raise ValueError("oracle must be assertion, asan_ubsan, or tsan")
    harness = harness.resolve()
    if not (harness / "build.sh").is_file() or harness.is_symlink():
        raise ValueError("harness must be a directory containing build.sh")
    if any(p.is_symlink() for p in harness.rglob("*")):
        raise TamperError("harness symlinks are unsupported")
    out = _output(out, [repo, harness])
    config.WORK.mkdir(parents=True, exist_ok=True)
    variant = {"assertion": "plain", "asan_ubsan": "asan_ubsan", "tsan": "tsan"}[oracle]
    with tempfile.TemporaryDirectory(prefix="seal-", dir=config.WORK) as directory:
        work = Path(directory)
        tree = work / "source"
        original_hash = _copy_source(repo, tree)
        shutil.copytree(harness, tree / "proofsmith_harness")
        metadata = {"schema": "proofsmith.verifier/1", "system": "supplied", "instance_id": repo.name,
                    "status": "submitted", "oracle": oracle, "variant": variant, "signature": None,
                    "harness_source": "user supplied; no model generation", "gate_recipe": recipe.model_dump(),
                    "model": None, "cost_usd": 0.0,
                    "created_at": datetime.now(timezone.utc).isoformat()}
        draft = freeze(tree, metadata, work / "draft")
        result = verify_bundle(draft, tree, recipe, config.RUNTIME_N, work / "qualification")
        decision = decide(result.runs, config.RUNTIME_K, oracle)
        signature = decision.signature or ""
        baseline = _record(result, work / "qualification", out, "baseline", oracle, signature)
        unchanged = _unchanged(tree, original_hash, draft)
        accepted = (unchanged and result.build_ok and len(result.runs) == config.RUNTIME_N and decision.accepted and
                    baseline["unexpected_failures"] == 0)
        metadata.update(status="accepted" if accepted else "abstained", signature=signature,
                        abstain_reason=None if accepted else decision.reason,
                        runtime={"n": config.RUNTIME_N, "k": config.RUNTIME_K, "fails": result.fails,
                                 "signatures": dict(Counter(r.evidence.signature for r in result.runs))})
        # Re-freeze from the pre-execution source snapshot, keeping its original hash.
        metadata["buggy_tree_sha256"] = original_hash
        bundle = freeze(tree, metadata, out / "bundle")
        frozen = json.loads((bundle / "verifier.json").read_text())
        frozen["buggy_tree_sha256"] = original_hash
        _json(bundle / "verifier.json", frozen)
        receipt = {"schema": "proofsmith.patch-gate/1", "operation": "seal",
                   "status": "VERIFIED" if accepted else "INCONCLUSIVE",
                   "reason": "Stable application oracle qualified" if accepted else
                             "Check changed the source or its own harness" if not unchanged else "Check did not qualify: " + decision.reason,
                   "created_at": datetime.now(timezone.utc).isoformat(), "bundle_id": bundle_id(bundle),
                   "oracle": oracle, "signature": signature, "baseline_sha256": original_hash,
                   "harness_source": metadata["harness_source"], "recipe": recipe.model_dump(),
                   "policy": {"n": config.RUNTIME_N, "target_minimum": config.RUNTIME_K}, "baseline": baseline,
                   "source_and_harness_unchanged": unchanged}
    return _finish(out, receipt)


def check_patch(bundle: Path, baseline: Path, candidate: Path, recipe: BuildRecipe, out: Path,
                expected_bundle_id: str | None = None, n: int = config.EVAL_N) -> dict:
    """Reproduce the frozen target on the baseline, then test the candidate on copies."""
    if n < config.EVAL_N or n > 100:
        raise ValueError("patch gate requires between 20 and 100 runs per tree")
    out = _output(out, [bundle, baseline, candidate])
    receipt = {"schema": "proofsmith.patch-gate/1", "operation": "check_patch",
               "status": "INCONCLUSIVE", "created_at": datetime.now(timezone.utc).isoformat(),
               "policy": {"n": n, "target_minimum": math.ceil(n * 0.8), "candidate_max_failures": 0},
               "identity_pinned": expected_bundle_id is not None, "recipe": recipe.model_dump()}
    try:
        if expected_bundle_id is None:
            raise ValueError("provide the trusted bundle identity recorded before patching")
        identity = bundle_id(bundle)
        receipt["bundle_id"] = identity
        if expected_bundle_id is not None and identity != expected_bundle_id:
            raise TamperError("bundle identity differs from the pre-patch identity")
        meta = load_bundle(bundle)
        receipt.update(oracle=meta.get("oracle"), signature=meta.get("signature"),
                       harness_source=meta.get("harness_source", meta.get("system", "unknown")))
        if meta.get("status") not in {"accepted", "submitted"}:
            raise ValueError("bundle has no submitted or accepted check")
        oracle = meta.get("oracle")
        signature = meta.get("signature")
        if oracle not in ELIGIBLE or not signature:
            raise ValueError("bundle must contain a qualified oracle signature")
        expected_variant = {"assertion": "plain", "asan_ubsan": "asan_ubsan", "tsan": "tsan"}[oracle]
        if meta.get("variant") != expected_variant:
            raise ValueError("bundle oracle and compiler variant disagree")
        if meta.get("gate_recipe") is not None and meta["gate_recipe"] != recipe.model_dump():
            raise ValueError("build recipe differs from the qualified recipe")
        config.WORK.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(prefix="patch-gate-", dir=config.WORK) as directory:
            work = Path(directory)
            # Snapshot both trees before running any untrusted harness code.
            receipt["baseline_sha256"] = _copy_source(baseline, work / "baseline")
            receipt["candidate_sha256"] = _copy_source(candidate, work / "candidate")
            if receipt["baseline_sha256"] != meta.get("buggy_tree_sha256"):
                raise ValueError("baseline does not match the source on which this check was frozen")
            (out / "bundle").mkdir()
            shutil.copyfile(bundle / "verifier.json", out / "bundle/verifier.json")
            shutil.copytree(bundle / "harness", out / "bundle/harness")
            if bundle_id(out / "bundle") != expected_bundle_id:
                raise TamperError("bundle changed while the gate was copying it")
            for side in ("baseline", "candidate"):
                result = verify_bundle(out / "bundle", work / side, recipe, n, work / (side + "-run"))
                receipt[side] = _record(result, work / (side + "-run"), out, side, oracle, signature)
                if result.build_ok and not _unchanged(work / side, receipt[side + "_sha256"], out / "bundle"):
                    receipt["reason"] = side + " check changed the source or its frozen harness"
                    return _finish(out, receipt)
                if not result.build_ok or len(result.runs) != n:
                    receipt["reason"] = side + " could not build or complete the required runs"
                    return _finish(out, receipt)
                if receipt[side]["unexpected_failures"]:
                    receipt["reason"] = side + " failed for a reason other than the frozen target"
                    return _finish(out, receipt)
                if side == "baseline" and receipt[side]["target_failures"] < receipt["policy"]["target_minimum"]:
                    receipt["reason"] = "Original failure is not reproducible at the required threshold"
                    return _finish(out, receipt)
            receipt["source_and_harness_unchanged"] = True
            if receipt["candidate"]["fails"]:
                receipt.update(status="REJECTED", reason="The frozen target still fires on the proposed fix")
            else:
                receipt.update(status="VERIFIED", reason="Original target reproduced; candidate passed every run")
        if snapshot_sha256(baseline) != receipt["baseline_sha256"] or snapshot_sha256(candidate) != receipt["candidate_sha256"]:
            receipt.update(status="INCONCLUSIVE", reason="Input source changed while the gate was running")
    except (TamperError, ValueError, KeyError, OSError, RuntimeError) as exc:
        receipt.update(status="INCONCLUSIVE", reason=f"{type(exc).__name__}: {exc}")
    return _finish(out, receipt)


def check_receipt(directory: Path, expected_manifest_sha256: str | None = None) -> dict:
    """Check every packaged evidence byte against its manifest. No compiler or API."""
    directory = directory.resolve()
    identity = hashlib.sha256((directory / "manifest.json").read_bytes()).hexdigest()
    if expected_manifest_sha256 is not None and identity != expected_manifest_sha256:
        raise TamperError("manifest differs from its trusted identity")
    manifest = json.loads((directory / "manifest.json").read_text())
    declared = manifest["files"]
    actual = {p.relative_to(directory).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
              for p in directory.rglob("*") if p.is_file() and p != directory / "manifest.json"}
    if any(p.is_symlink() for p in directory.rglob("*")) or actual != declared:
        raise TamperError("evidence file set or hash differs from its manifest")
    return {"matches": True, "files_checked": len(actual),
            "manifest_sha256": identity}
