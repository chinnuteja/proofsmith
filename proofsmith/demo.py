"""Deterministic orderd deadlock demo. No model calls."""

from __future__ import annotations

import json
import shutil
import subprocess
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

from proofsmith.config import REPO, RESULTS, RUNTIME_K, WORK
from proofsmith.datasets.schema import Instance, apply_patch, materialize
from proofsmith.freeze import freeze, load_bundle, verify_bundle
from proofsmith.oracles.acceptance import decide
from proofsmith.oracles.builds import build_variant
from proofsmith.oracles.runner import run_n
from proofsmith.oracles.variants import VARIANTS

_VARIANTS = ("timing_backoff", "scoped_cancel", "consistent_order")
_ROWS = ("buggy", "timing_backoff", "scoped_cancel", "consistent_order")


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8", newline="\n")


def _ctest(build_dir: Path, command: str) -> tuple[int, int, str]:
    proc = subprocess.run(
        command.split(),
        cwd=build_dir,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        check=False,
        text=True,
    )
    text = proc.stdout
    import re

    match = re.search(r"(\d+) tests failed out of (\d+)", text)
    if not match:
        raise RuntimeError(f"ctest summary missing\n{text}")
    failed = int(match.group(1))
    total = int(match.group(2))
    return total - failed, total, text


def _stress(repo: Path, build_dir: Path, work: Path) -> tuple[int, int]:
    work.mkdir(parents=True, exist_ok=True)
    binary = work / "stress"
    flags = VARIANTS["plain"]
    cmd = [
        "clang++",
        "-std=c++17",
        *flags.cxxflags.split(),
        "-I",
        str(repo),
        str(REPO / "cases" / "orderd" / "stress" / "stress.cpp"),
        str(Path(build_dir) / "liborderd_core.a"),
        "-o",
        str(binary),
        *flags.ldflags.split(),
        "-pthread",
    ]
    proc = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, check=False, text=True)
    if proc.returncode != 0:
        raise RuntimeError(f"stress compile failed\n{proc.stdout}")
    runs = run_n(binary, "plain", 20, 5, repo, str(repo.resolve()), work / "logs")
    fails = sum(1 for run in runs if run.timed_out or run.exit_code != 0)
    return fails, 20


def _install_harness(repo: Path) -> None:
    src = REPO / "cases" / "orderd" / "reference_harness"
    dest = repo / "proofsmith_harness"
    if dest.exists():
        shutil.rmtree(dest)
    dest.mkdir()
    shutil.copy2(src / "harness.cpp", dest / "harness.cpp")
    shutil.copy2(src / "build.sh", dest / "build.sh")


def run_orderd() -> Path:
    root = WORK / "demo" / "orderd"
    if root.exists():
        shutil.rmtree(root)
    root.mkdir(parents=True)
    instance = Instance.model_validate_json((REPO / "cases" / "orderd" / "instance.json").read_text(encoding="utf-8"))
    recipe = instance.build
    trees: dict[str, Path] = {"buggy": materialize(instance, root / "buggy")}
    for name in _VARIANTS:
        dest = materialize(instance, root / name)
        apply_patch(dest, REPO / "cases" / "orderd" / "variants" / f"{name}.patch")
        trees[name] = dest

    _install_harness(trees["buggy"])
    bundle = freeze(
        trees["buggy"],
        {
            "schema": "proofsmith.verifier/1",
            "system": "reference",
            "instance_id": instance.id,
            "status": "accepted",
            "abstain_reason": None,
            "oracle": "tsan",
            "variant": "tsan",
            "signature": "",
            "runtime": {"n": 10, "k": RUNTIME_K, "fails": 0, "signatures": {}},
            "model": None,
            "usage": {
                "prompt_tokens": 0,
                "completion_tokens": 0,
                "reasoning_tokens": 0,
                "cache_hit_tokens": 0,
            },
            "cost_usd": 0.0,
            "wall_s": 0.0,
            "trajectory": None,
            "created_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        },
        root / "bundle",
    )

    rows: dict[str, dict] = {}
    buggy_runs = None
    raw_report = ""
    for name in _ROWS:
        tree = trees[name]
        print(f"== {name}: plain build, ctest, stress")
        plain = build_variant(tree, "plain", recipe, root / "out" / name)
        if not plain.ok:
            log = plain.log_path.read_text(encoding="utf-8", errors="replace") if plain.log_path.is_file() else ""
            raise RuntimeError(f"plain build failed for {name}\n{log[-4000:]}")
        passed, total, _ctest_text = _ctest(plain.build_dir, recipe.test_command or "ctest --output-on-failure -j4")
        stress_fails, stress_n = _stress(tree, plain.build_dir, root / "stress" / name)
        print(f"== {name}: verify tsan x20")
        verified = verify_bundle(bundle, tree, recipe, 20, root / "verify" / name)
        if not verified.build_ok:
            raise RuntimeError(f"verifier build failed for {name}")
        rows[name] = {
            "ctest": {"passed": passed, "total": total},
            "stress": {"fails": stress_fails, "n": stress_n},
            "verifier": {"fails": verified.fails, "n": verified.n},
        }
        print(
            f"{name}: ctest {passed}/{total} stress {stress_fails}/{stress_n} "
            f"verifier {verified.fails}/{verified.n}"
        )
        if name == "buggy":
            buggy_runs = verified.runs
            for run in verified.runs:
                text = Path(run.output_path).read_text(encoding="utf-8", errors="replace")
                if "lock-order-inversion" in text:
                    raw_report = text
                    break
            if not raw_report and verified.runs:
                raw_report = Path(verified.runs[0].output_path).read_text(encoding="utf-8", errors="replace")

    if buggy_runs is None:
        raise RuntimeError("buggy verifier produced no runs")
    sample = buggy_runs[:10]
    decision = decide(sample, RUNTIME_K, "tsan")
    fail_count = sum(1 for run in sample if run.timed_out or run.exit_code != 0)
    signatures = Counter(
        run.evidence.signature
        for run in sample
        if run.evidence.kind.startswith("tsan:") and run.evidence.app_frames
    )
    loaded = load_bundle(bundle)
    loaded["signature"] = decision.signature or ""
    loaded["runtime"] = {
        "n": 10,
        "k": RUNTIME_K,
        "fails": fail_count,
        "signatures": dict(signatures),
    }
    loaded["status"] = "accepted" if decision.accepted else "submitted"
    _write_json(bundle / "verifier.json", loaded)

    strip = [
        bool(
            decision.signature
            and run.evidence.signature == decision.signature
            and run.evidence.kind.startswith("tsan:")
        )
        for run in sample
    ]
    payload = {
        "schema": "proofsmith.demo/1",
        "instance_id": instance.id,
        "harness_source": "reference",
        "oracle": "tsan",
        "issue": {"title": instance.issue.title, "body": instance.issue.body},
        "decision": {
            "accepted": decision.accepted,
            "signature": decision.signature,
            "count": decision.count,
            "n": decision.n,
            "reason": decision.reason,
        },
        "verifier": {
            "signature": decision.signature or "",
            "runtime": {"n": 10, "k": RUNTIME_K, "fails": fail_count, "signatures": dict(signatures)},
            "files": loaded["files"],
        },
        "strip": strip,
        "rows": rows,
        "raw_report_buggy": raw_report,
        "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
    }
    dest = RESULTS / "demo" / "orderd.json"
    _write_json(dest, payload)
    print(dest)
    return dest
