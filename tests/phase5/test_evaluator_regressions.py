"""Regression checks for Git fixes and real LLVM coverage (no model calls)."""
import json
from pathlib import Path

import pytest

import proofsmith.eval.evaluator as evaluator
from proofsmith.config import REPO, WORK
from proofsmith.datasets.schema import HiddenInstance, Instance, materialize
from proofsmith.freeze import freeze


def test_git_fix_uses_hidden_diff():
    instance = Instance.model_validate_json((REPO / "data/trackB/instances/spdlog-1570.json").read_text())
    hidden = HiddenInstance.model_validate_json((REPO / "data/trackB/hidden/spdlog-1570.json").read_text())
    assert "daily_file_sink" in evaluator._read_fix_diff(hidden, instance)


def test_missing_diff_is_an_error():
    hidden = HiddenInstance.model_validate({"schema": "proofsmith.hidden/1", "id": "x",
        "fixed": {"kind": "git", "commit": "abc"}, "bug_class": "race", "fix_files": []})
    with pytest.raises(RuntimeError, match="alignment cannot be scored"):
        evaluator._read_fix_diff(hidden)


def test_llvm_function_regions_are_at_block_level(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    payload = {"data": [{"files": [{"filename": str(repo / "a.cpp")}], "functions": [
        {"name": "_Z3foov", "count": 1, "filenames": [str(repo / "a.cpp")],
         "regions": [[8, 1, 20, 2, 1, 0, 0, 0]]},
        {"name": "not_run", "count": 0, "filenames": [str(repo / "a.cpp")],
         "regions": [[30, 1, 35, 2, 0, 0, 0, 0]]},
        {"name": "main", "count": 1, "filenames": [str(repo / "proofsmith_harness/harness.cpp")],
         "regions": [[1, 1, 5, 2, 1, 0, 0, 0]]},
    ]}]}
    hits = evaluator._parse_coverage(payload, repo)
    assert [(h.file, h.start, h.end) for h in hits] == [("a.cpp", 8, 20)]


@pytest.mark.slow
def test_failed_ps_check_flushes_real_coverage(tmp_path):
    instance = Instance.model_validate_json((REPO / "cases/rounding-ticks/instance.json").read_text())
    hidden = HiddenInstance.model_validate_json((REPO / "cases/rounding-ticks/hidden/hidden.json").read_text())
    repo = materialize(instance, WORK / "regressions/coverage/src")
    harness = repo / "proofsmith_harness"
    harness.mkdir()
    (harness / "harness.cpp").write_text('#include "ticks.h"\n#include "proofsmith_check.h"\nint main(){ PS_CHECK(to_ticks(0.29,0.01)==29); }\n')
    (harness / "build.sh").write_text('''#!/usr/bin/env bash
set -euo pipefail
mkdir -p "$PS_OUT"
"$PS_CXX" $PS_CXXFLAGS -std=c++17 -I"$PS_REPO" -I"$PS_INCLUDE" "$PS_REPO/proofsmith_harness/harness.cpp" "$PS_REPO/ticks.cpp" $PS_LDFLAGS -o "$PS_OUT/harness"
''')
    bundle = freeze(repo, {"system": "reference", "status": "submitted", "variant": "plain"}, tmp_path / "bundle")
    verdict = evaluator.evaluate(bundle, instance, hidden, WORK / "regressions/coverage/eval")
    assert verdict.f2p
    assert verdict.alignment["strict"], verdict.as_dict()
    assert any(hit["via"] == "coverage" for hit in verdict.alignment["hits"])
