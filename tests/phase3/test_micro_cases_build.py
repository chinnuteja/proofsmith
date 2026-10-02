"""Micro cases build under every variant, and existing tests pass on both trees."""

from __future__ import annotations

import subprocess

import pytest

from proofsmith.config import REPO, WORK
from proofsmith.datasets.schema import HiddenInstance, Instance, apply_patch, materialize
from proofsmith.oracles.builds import build_variant

pytestmark = [pytest.mark.slow, pytest.mark.timeout(1800)]

_CASES = ("uaf-lru", "race-stats", "ub-notional", "rounding-ticks", "vague-perf")
_VARIANTS = ("plain", "asan_ubsan", "tsan")


def _load(case_id: str) -> tuple[Instance, HiddenInstance]:
    instance = Instance.model_validate_json(
        (REPO / "cases" / case_id / "instance.json").read_text(encoding="utf-8")
    )
    hidden = HiddenInstance.model_validate_json(
        (REPO / "cases" / case_id / "hidden" / "hidden.json").read_text(encoding="utf-8")
    )
    return instance, hidden


def _ctest(build_dir, command: str) -> None:
    proc = subprocess.run(
        command.split(),
        cwd=build_dir,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        check=False,
        text=True,
        timeout=120,
    )
    assert proc.returncode == 0, proc.stdout[-2000:]


def _build_and_test(repo, instance: Instance, out_root) -> None:
    for variant in _VARIANTS:
        built = build_variant(repo, variant, instance.build, out_root)
        log = ""
        if built.log_path.is_file():
            log = built.log_path.read_text(encoding="utf-8", errors="replace")[-2000:]
        assert built.ok, f"{variant}\n{log}"
        _ctest(built.build_dir, instance.build.test_command or "ctest --output-on-failure -j4")


def test_micro_cases_build_and_tests_pass():
    for case_id in _CASES:
        instance, _hidden = _load(case_id)
        root = WORK / "micro-cases" / case_id
        buggy = materialize(instance, root / "buggy")
        _build_and_test(buggy, instance, root / "buggy-out")
        patch = REPO / "cases" / case_id / "hidden" / "fix.patch"
        if not patch.is_file():
            assert case_id == "vague-perf"
            continue
        fixed = materialize(instance, root / "fixed")
        apply_patch(fixed, patch)
        _build_and_test(fixed, instance, root / "fixed-out")
