"""Hidden evaluator against the orderd trees. No model calls."""

from __future__ import annotations

import shutil
from pathlib import Path

import pytest

from proofsmith.config import REPO, WORK
from proofsmith.datasets.schema import HiddenInstance, Instance, materialize
from proofsmith.eval.evaluator import evaluate
from proofsmith.freeze import freeze

pytestmark = [pytest.mark.slow, pytest.mark.timeout(1800)]

_STANDALONE = """#!/usr/bin/env bash
set -euo pipefail
mkdir -p "$PS_OUT"
# shellcheck disable=SC2086
"$PS_CXX" $PS_CXXFLAGS -std=c++17 "$PS_REPO/proofsmith_harness/harness.cpp" $PS_LDFLAGS -o "$PS_OUT/harness"
"""

_FIXED_COMPILE_FAIL = """#!/usr/bin/env bash
set -euo pipefail
if grep -q 'scoped_lock' "$PS_REPO/order_book.cpp"; then
  echo "fixed tree changed the lock" >&2
  exit 1
fi
mkdir -p "$PS_OUT"
# shellcheck disable=SC2086
"$PS_CXX" $PS_CXXFLAGS -std=c++17 "$PS_REPO/proofsmith_harness/harness.cpp" $PS_LDFLAGS -o "$PS_OUT/harness"
"""


def _orderd() -> Instance:
    return Instance.model_validate_json((REPO / "cases" / "orderd" / "instance.json").read_text(encoding="utf-8"))


def _hidden() -> HiddenInstance:
    return HiddenInstance.model_validate_json(
        (REPO / "cases" / "orderd" / "hidden" / "hidden.json").read_text(encoding="utf-8")
    )


def _work(name: str) -> Path:
    path = WORK / "eval" / "phase5" / name
    if path.exists():
        shutil.rmtree(path)
    path.mkdir(parents=True)
    return path


def _meta(system: str, variant: str) -> dict:
    return {
        "schema": "proofsmith.verifier/1",
        "system": system,
        "instance_id": "orderd-deadlock",
        "status": "submitted",
        "abstain_reason": None,
        "oracle": "tsan" if variant == "tsan" else None,
        "variant": variant,
        "signature": None,
        "runtime": {"n": 0, "k": 0, "fails": 0, "signatures": {}},
        "flags": {"cxxflags": "", "ldflags": "", "env": {}},
        "model": "fake",
        "usage": {
            "prompt_tokens": 0,
            "completion_tokens": 0,
            "reasoning_tokens": 0,
            "cache_hit_tokens": 0,
        },
        "cost_usd": 0.0,
        "wall_s": 0.0,
        "trajectory": None,
        "created_at": "2026-10-02T00:00:00Z",
    }


def _freeze(tmp_path: Path, script: str, source: str, variant: str, system: str = "b0") -> Path:
    repo = materialize(_orderd(), tmp_path / "src")
    harness = repo / "proofsmith_harness"
    harness.mkdir()
    (harness / "build.sh").write_text(script, encoding="utf-8", newline="\n")
    (harness / "harness.cpp").write_text(source, encoding="utf-8", newline="\n")
    return freeze(repo, _meta(system, variant), tmp_path / "bundle")


def test_reference_bundle_is_aligned_fail_to_pass(tmp_path: Path):
    repo = materialize(_orderd(), tmp_path / "src")
    src = REPO / "cases" / "orderd" / "reference_harness"
    harness = repo / "proofsmith_harness"
    harness.mkdir()
    shutil.copy2(src / "harness.cpp", harness / "harness.cpp")
    shutil.copy2(src / "build.sh", harness / "build.sh")
    bundle = freeze(repo, _meta("reference", "tsan"), tmp_path / "bundle")
    verdict = evaluate(bundle, _orderd(), _hidden(), _work("reference"))
    assert verdict.f2p is True, verdict.as_dict()
    assert verdict.alignment["strict"] is True
    blob = " ".join(
        f"{hit.get('function', '')} {hit.get('evidence', '')}" for hit in verdict.alignment["hits"]
    )
    assert "cancel" in blob


def test_always_fail_is_not_fail_to_pass(tmp_path: Path):
    bundle = _freeze(tmp_path, _STANDALONE, "int main() { return 1; }\n", "plain")
    verdict = evaluate(bundle, _orderd(), _hidden(), _work("always"))
    assert verdict.build_ok_buggy is True
    assert verdict.build_ok_fixed is True
    assert verdict.buggy_fails == 20
    assert verdict.fixed_fails == 20
    assert verdict.f2p is False


def test_flaky_bundle_is_not_fail_to_pass(tmp_path: Path):
    source = """#include <random>
int main() {
  std::random_device device;
  if (device() % 2U) return 1;
  return 0;
}
"""
    bundle = _freeze(tmp_path, _STANDALONE, source, "plain")
    verdict = evaluate(bundle, _orderd(), _hidden(), _work("flaky"))
    assert verdict.f2p is False


def test_tampered_bundle_records_the_error(tmp_path: Path):
    bundle = _freeze(tmp_path, _STANDALONE, "int main() { return 1; }\n", "plain")
    cpp = bundle / "harness" / "harness.cpp"
    cpp.write_text(cpp.read_text(encoding="utf-8") + "int extra = 1;\n", encoding="utf-8", newline="\n")
    verdict = evaluate(bundle, _orderd(), _hidden(), _work("tamper"))
    assert verdict.f2p is False
    assert verdict.error


def test_fixed_tree_compile_failure(tmp_path: Path):
    bundle = _freeze(tmp_path, _FIXED_COMPILE_FAIL, "int main() { return 1; }\n", "plain")
    verdict = evaluate(bundle, _orderd(), _hidden(), _work("fixed-compile"))
    assert verdict.build_ok_fixed is False
    assert verdict.f2p is False


def test_systems_and_pipeline_do_not_import_the_evaluator():
    for name in ("systems.py", "pipeline.py"):
        text = (REPO / "proofsmith" / name).read_text(encoding="utf-8")
        assert "proofsmith.eval" not in text
        assert "eval.evaluator" not in text
        assert "eval.alignment" not in text
