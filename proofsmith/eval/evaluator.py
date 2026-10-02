"""Run a frozen bundle on the buggy tree and the hidden fixed tree.

This is the only component that reads the fix. Fail-to-pass uses the
contract rule and does not depend on alignment.
"""

from __future__ import annotations

import json
import shutil
import subprocess
from collections import Counter
from dataclasses import dataclass
from pathlib import Path

from proofsmith.config import EVAL_BUGGY_K, EVAL_FIXED_MAX_FAILS, EVAL_N, REPO, RUN_TIMEOUT_S
from proofsmith.datasets.schema import HiddenInstance, Instance, apply_patch, materialize
from proofsmith.eval.alignment import FuncRange, align, changed_functions
from proofsmith.freeze import TamperError, load_bundle
from proofsmith.harness import compile_harness
from proofsmith.oracles.builds import build_variant
from proofsmith.oracles.runner import run_n, variant_env
from proofsmith.oracles.signature import Frame


@dataclass
class Verdict:
    instance_id: str
    system: str
    track: str
    bundle_status: str
    build_ok_buggy: bool
    build_ok_fixed: bool
    buggy_fails: int
    fixed_fails: int
    n: int
    f2p: bool
    alignment: dict
    oracle: str | None
    evidence_kinds: dict
    cost_usd: float
    wall_s: float
    error: str | None

    def as_dict(self) -> dict:
        return {
            "schema": "proofsmith.verdict/1",
            "instance_id": self.instance_id,
            "system": self.system,
            "track": self.track,
            "bundle_status": self.bundle_status,
            "build_ok_buggy": self.build_ok_buggy,
            "build_ok_fixed": self.build_ok_fixed,
            "buggy_fails": self.buggy_fails,
            "fixed_fails": self.fixed_fails,
            "n": self.n,
            "f2p": self.f2p,
            "alignment": self.alignment,
            "oracle": self.oracle,
            "evidence_kinds": self.evidence_kinds,
            "cost_usd": self.cost_usd,
            "wall_s": self.wall_s,
            "error": self.error,
        }


def _empty_alignment(unknown: bool = False) -> dict:
    return {"strict": False, "relaxed": False, "unknown": unknown, "hits": [], "changed": []}


def _verdict(
    instance: Instance,
    system: str,
    status: str,
    *,
    build_ok_buggy: bool = False,
    build_ok_fixed: bool = False,
    buggy_fails: int = 0,
    fixed_fails: int = 0,
    n: int = 0,
    alignment: dict | None = None,
    oracle: str | None = None,
    evidence_kinds: dict | None = None,
    cost_usd: float = 0.0,
    wall_s: float = 0.0,
    error: str | None = None,
) -> Verdict:
    aligned = alignment if alignment is not None else _empty_alignment()
    f2p = bool(
        build_ok_buggy
        and build_ok_fixed
        and buggy_fails >= EVAL_BUGGY_K
        and fixed_fails <= EVAL_FIXED_MAX_FAILS
    )
    return Verdict(
        instance.id,
        system,
        instance.track,
        status,
        build_ok_buggy,
        build_ok_fixed,
        buggy_fails,
        fixed_fails,
        n,
        f2p,
        aligned,
        oracle,
        evidence_kinds or {},
        float(cost_usd or 0.0),
        float(wall_s or 0.0),
        error,
    )


def _resolve(path: str) -> Path:
    candidate = Path(path)
    if not candidate.is_absolute():
        candidate = REPO / candidate
    return candidate


def _read_fix_diff(hidden: HiddenInstance) -> str:
    if hidden.fixed.kind == "patch" and hidden.fixed.path:
        path = _resolve(hidden.fixed.path)
        if path.is_file():
            return path.read_text(encoding="utf-8", errors="replace")
    return ""


def _changed_payload(ranges: list[FuncRange]) -> list[dict]:
    return [
        {"function": item.name, "file": item.file, "start": item.start, "end": item.end}
        for item in ranges
    ]


def _copy_tree(src: Path, dest: Path) -> None:
    if dest.exists():
        shutil.rmtree(dest)
    shutil.copytree(src, dest, ignore=shutil.ignore_patterns(".git"))


def _materialize_fixed(instance: Instance, hidden: HiddenInstance, buggy: Path, dest: Path) -> None:
    fixed = hidden.fixed
    if fixed.kind == "git":
        if not instance.source.url or not fixed.commit:
            raise RuntimeError("git fix requires a repository url and a fixed commit")
        cloned = instance.model_copy(
            update={"source": instance.source.model_copy(update={"commit": fixed.commit})}
        )
        materialize(cloned, dest)
        return
    if fixed.kind == "dir":
        if not fixed.path:
            raise RuntimeError("dir fix requires a path")
        if dest.exists():
            shutil.rmtree(dest)
        shutil.copytree(_resolve(fixed.path), dest)
        return
    if not fixed.path:
        raise RuntimeError("patch fix requires a path")
    _copy_tree(buggy, dest)
    apply_patch(dest, _resolve(fixed.path))


def _install_harness(repo: Path, bundle_dir: Path) -> None:
    dest = repo / "proofsmith_harness"
    if dest.exists():
        shutil.rmtree(dest)
    shutil.copytree(bundle_dir / "harness", dest)


def _failed(run) -> bool:
    return bool(run.timed_out or run.exit_code != 0)


def _coverage_hits(repo: Path, recipe, work: Path) -> list[FuncRange] | None:
    """Functions executed by one coverage run.

    None means the run timed out. An empty list means coverage produced no
    executed functions, or the coverage tools could not be read.
    """
    built = build_variant(repo, "coverage", recipe, work / "coverage-build")
    if not built.ok:
        return []
    compiled = compile_harness(repo, built, "coverage", work / "coverage-harness")
    if not compiled.ok or compiled.binary is None:
        return []
    profraw = work / "coverage.profraw"
    if profraw.exists():
        profraw.unlink()
    env = variant_env("coverage")
    env["LLVM_PROFILE_FILE"] = str(profraw)
    try:
        subprocess.run(
            [str(compiled.binary)],
            cwd=repo,
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            timeout=RUN_TIMEOUT_S,
            check=False,
        )
    except subprocess.TimeoutExpired:
        return None
    if not profraw.is_file():
        return []
    profdata = work / "coverage.profdata"
    merged = subprocess.run(
        ["llvm-profdata", "merge", "-sparse", str(profraw), "-o", str(profdata)],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        check=False,
        text=True,
    )
    if merged.returncode != 0 or not profdata.is_file():
        return []
    exported = subprocess.run(
        [
            "llvm-cov",
            "export",
            "-format=text",
            "-instr-profile",
            str(profdata),
            str(compiled.binary),
        ],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        check=False,
        text=True,
    )
    payload_text = exported.stdout
    if exported.returncode != 0 or not payload_text.strip().startswith("{"):
        exported = subprocess.run(
            ["llvm-cov", "export", "-instr-profile", str(profdata), str(compiled.binary)],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            check=False,
            text=True,
        )
        payload_text = exported.stdout
    try:
        payload = json.loads(payload_text)
    except json.JSONDecodeError:
        return []
    hits: list[FuncRange] = []
    blocks = payload.get("data") if isinstance(payload, dict) else None
    if not isinstance(blocks, list):
        return []
    for block in blocks:
        if not isinstance(block, dict):
            continue
        for item in block.get("files") or []:
            if not isinstance(item, dict):
                continue
            filename = str(item.get("filename") or "")
            try:
                rel = Path(filename).resolve().relative_to(repo.resolve()).as_posix()
            except ValueError:
                rel = Path(filename).as_posix()
            for fn in item.get("functions") or []:
                if not isinstance(fn, dict):
                    continue
                try:
                    count = int(fn.get("count") or 0)
                except (TypeError, ValueError):
                    count = 0
                if count <= 0:
                    continue
                start, end = 1, 1
                regions = fn.get("regions") or []
                if regions and isinstance(regions[0], list) and len(regions[0]) >= 3:
                    start = int(regions[0][0])
                    end = int(regions[0][2])
                hits.append(FuncRange(str(fn.get("name") or ""), rel, start, end))
    return hits


def _run_tree(repo: Path, bundle_dir: Path, variant: str, recipe, work: Path) -> tuple[bool, list]:
    _install_harness(repo, bundle_dir)
    built = build_variant(repo, variant, recipe, work / "build")
    if not built.ok:
        return False, []
    compiled = compile_harness(repo, built, variant, work / "harness-out")
    if not compiled.ok or compiled.binary is None:
        return False, []
    runs = run_n(
        compiled.binary,
        variant,
        EVAL_N,
        RUN_TIMEOUT_S,
        repo,
        str(repo.resolve()),
        work / "logs",
    )
    return True, runs


def _alignment(buggy: Path, diff: str, runs: list, recipe, work: Path) -> dict:
    changed = changed_functions(buggy, diff) if diff else []
    frames: list[Frame] = []
    for run in runs:
        if not _failed(run):
            continue
        frames.extend(run.evidence.app_frames)
    if frames:
        scored = align(frames, [], changed, str(buggy.resolve()))
    else:
        coverage = _coverage_hits(buggy, recipe, work / "cov") if runs else []
        scored = align([], coverage, changed, str(buggy.resolve()))
    payload = scored.as_dict()
    payload["changed"] = _changed_payload(changed)
    return payload


def evaluate(bundle_dir: Path, instance: Instance, hidden: HiddenInstance, work: Path) -> Verdict:
    bundle_dir = Path(bundle_dir)
    work = Path(work) / instance.id / (bundle_dir.name or "bundle")
    system = "unknown"
    try:
        meta = load_bundle(bundle_dir)
    except (TamperError, OSError, json.JSONDecodeError, KeyError) as exc:
        system = _peek_system(bundle_dir) or system
        return _verdict(instance, system, "error", error=str(exc))

    system = str(meta.get("system") or system)
    status = str(meta.get("status") or "")
    oracle = meta.get("oracle")
    cost = float(meta.get("cost_usd") or 0.0)
    wall = float(meta.get("wall_s") or 0.0)
    if status in {"abstained", "skipped"}:
        return _verdict(
            instance,
            system,
            status,
            oracle=oracle if isinstance(oracle, str) else None,
            cost_usd=cost,
            wall_s=wall,
        )

    variant = meta.get("variant")
    if not isinstance(variant, str) or not variant:
        return _verdict(
            instance,
            system,
            status or "gave_up",
            oracle=oracle if isinstance(oracle, str) else None,
            cost_usd=cost,
            wall_s=wall,
            error="bundle has no build variant",
        )

    root = work
    if root.exists():
        shutil.rmtree(root)
    root.mkdir(parents=True)
    buggy = materialize(instance, root / "buggy")
    try:
        _materialize_fixed(instance, hidden, buggy, root / "fixed")
    except Exception as exc:
        return _verdict(
            instance,
            system,
            status,
            oracle=oracle if isinstance(oracle, str) else None,
            cost_usd=cost,
            wall_s=wall,
            error=f"fixed tree: {exc}",
        )

    build_ok_buggy, buggy_runs = _run_tree(buggy, bundle_dir, variant, instance.build, root / "run-buggy")
    build_ok_fixed, fixed_runs = _run_tree(root / "fixed", bundle_dir, variant, instance.build, root / "run-fixed")
    buggy_fails = sum(1 for run in buggy_runs if _failed(run))
    fixed_fails = sum(1 for run in fixed_runs if _failed(run))
    kinds = Counter(run.evidence.kind for run in buggy_runs if _failed(run))
    try:
        alignment = _alignment(buggy, _read_fix_diff(hidden), buggy_runs, instance.build, root / "align")
    except Exception as exc:
        alignment = _empty_alignment(unknown=True)
        alignment["error"] = str(exc)
    return _verdict(
        instance,
        system,
        status,
        build_ok_buggy=build_ok_buggy,
        build_ok_fixed=build_ok_fixed,
        buggy_fails=buggy_fails,
        fixed_fails=fixed_fails,
        n=EVAL_N if (buggy_runs or fixed_runs or build_ok_buggy or build_ok_fixed) else 0,
        alignment=alignment,
        oracle=oracle if isinstance(oracle, str) else None,
        evidence_kinds=dict(kinds),
        cost_usd=cost,
        wall_s=wall,
    )


def _peek_system(bundle_dir: Path) -> str:
    path = Path(bundle_dir) / "verifier.json"
    if not path.is_file():
        return ""
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return ""
    system = payload.get("system")
    return str(system) if isinstance(system, str) else ""
