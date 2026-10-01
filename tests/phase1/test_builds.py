"""Real CMake builds of the orderd tree, including the build cache."""

from __future__ import annotations

import time

import pytest

from proofsmith.config import REPO, WORK
from proofsmith.datasets.schema import Instance
from proofsmith.oracles.builds import build_variant

pytestmark = pytest.mark.slow


def test_orderd_builds_and_cache_hit():
    instance = Instance.model_validate_json(
        (REPO / "cases" / "orderd" / "instance.json").read_text(encoding="utf-8")
    )
    repo = REPO / "cases" / "orderd" / "buggy"
    out = WORK / "test-builds" / "orderd"
    for variant in ("plain", "asan_ubsan", "tsan"):
        result = build_variant(repo, variant, instance.build, out)
        log = result.log_path.read_text(encoding="utf-8", errors="replace") if result.log_path.is_file() else ""
        assert result.ok, log[-4000:]
        assert result.compile_commands is not None and result.compile_commands.is_file()
    started = time.monotonic()
    again = build_variant(repo, "plain", instance.build, out)
    elapsed = time.monotonic() - started
    assert again.ok
    assert elapsed < 2, elapsed
