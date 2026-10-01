"""Freeze a harness into a verifier bundle and replay it."""

from __future__ import annotations

import hashlib
import json
import shutil
from dataclasses import dataclass
from pathlib import Path

from proofsmith.config import RUN_TIMEOUT_S
from proofsmith.datasets.schema import BuildRecipe
from proofsmith.harness import compile_harness
from proofsmith.oracles.builds import build_variant, snapshot_sha256
from proofsmith.oracles.runner import RunResult, run_n


class TamperError(Exception):
    pass


@dataclass
class VerifyResult:
    build_ok: bool
    fails: int
    n: int
    runs: list[RunResult]


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _harness_files(harness: Path) -> dict[str, str]:
    files: dict[str, str] = {}
    for path in sorted(harness.rglob("*")):
        if path.is_file() and not path.is_symlink():
            rel = "harness/" + path.relative_to(harness).as_posix()
            files[rel] = _sha256(path)
    return files


def freeze(repo: Path, meta: dict, out_dir: Path) -> Path:
    repo = Path(repo)
    out_dir = Path(out_dir)
    if out_dir.exists():
        shutil.rmtree(out_dir)
    out_dir.mkdir(parents=True)
    shutil.copytree(repo / "proofsmith_harness", out_dir / "harness")
    payload = dict(meta)
    payload["files"] = _harness_files(out_dir / "harness")
    payload["buggy_tree_sha256"] = snapshot_sha256(repo)
    text = json.dumps(payload, indent=2, sort_keys=True) + "\n"
    (out_dir / "verifier.json").write_text(text, encoding="utf-8", newline="\n")
    return out_dir


def load_bundle(path: Path) -> dict:
    path = Path(path)
    verifier_path = path / "verifier.json"
    if not verifier_path.is_file():
        raise TamperError("missing verifier.json")
    payload = json.loads(verifier_path.read_text(encoding="utf-8"))
    declared = payload.get("files")
    if not isinstance(declared, dict):
        raise TamperError("verifier files map missing")
    actual = _harness_files(path / "harness") if (path / "harness").is_dir() else {}
    missing = sorted(set(declared) - set(actual))
    extra = sorted(set(actual) - set(declared))
    if missing or extra:
        raise TamperError(f"file set mismatch missing={missing} extra={extra}")
    for name, digest in declared.items():
        if actual[name] != digest:
            raise TamperError(f"hash mismatch {name}")
    return payload


def _failed(run: RunResult) -> bool:
    return run.timed_out or run.exit_code != 0


def verify_bundle(bundle_dir: Path, repo: Path, recipe: BuildRecipe, n: int, work: Path) -> VerifyResult:
    meta = load_bundle(bundle_dir)
    variant = meta["variant"]
    repo = Path(repo)
    dest = repo / "proofsmith_harness"
    if dest.exists():
        shutil.rmtree(dest)
    shutil.copytree(Path(bundle_dir) / "harness", dest)
    work = Path(work)
    work.mkdir(parents=True, exist_ok=True)
    build = build_variant(repo, variant, recipe, work / "build")
    if not build.ok:
        return VerifyResult(False, 0, n, [])
    harness = compile_harness(repo, build, variant, work / "harness-out")
    if not harness.ok or harness.binary is None:
        return VerifyResult(False, 0, n, [])
    runs = run_n(
        harness.binary,
        variant,
        n,
        RUN_TIMEOUT_S,
        repo,
        str(repo.resolve()),
        work / "logs",
    )
    fails = sum(1 for run in runs if _failed(run))
    return VerifyResult(True, fails, n, runs)
