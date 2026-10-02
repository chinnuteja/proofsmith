"""Cached sanitizer builds for every Track B instance."""

from __future__ import annotations

import pytest

from proofsmith.datasets.check import check_dataset


@pytest.mark.slow
def test_check_dataset_builds():
    report = check_dataset("B")
    assert report.total >= 10
    assert report.counts["lifetime"] >= 4
    assert report.concurrency >= 4
    assert report.total == len(report.instances)
    for item in report.instances:
        assert item.schema_ok, item.problems
        assert item.issue_ok, item.problems
        assert item.separation_ok, item.problems
        for side in ("buggy", "fixed"):
            for variant in ("asan_ubsan", "tsan"):
                assert item.builds[side][variant], f"{item.id} {side} {variant}: {item.problems}"
        assert item.fix_size["files"] <= 5
        assert item.fix_size["lines"] <= 200
