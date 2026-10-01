"""Acceptance decisions on synthetic runs."""

from __future__ import annotations

from proofsmith.oracles.acceptance import decide
from proofsmith.oracles.runner import RunResult
from proofsmith.oracles.signature import Evidence, Frame


def _run(kind: str, signature: str, app_frames: int) -> RunResult:
    frames = [Frame(0, "f", "/repo/a.cpp", 1)] if app_frames else []
    evidence = Evidence(kind, frames, frames, signature)
    return RunResult(0, 1, False, 0.01, evidence, "log")


def test_stable_tsan_is_accepted():
    runs = [_run("tsan:lock-order-inversion", "tsan:lock-order-inversion|A@a.cpp", 1) for _ in range(10)]
    decision = decide(runs, 8, "tsan")
    assert decision.accepted
    assert decision.count == 10


def test_seven_of_ten_is_rejected():
    runs = [_run("tsan:data-race", "tsan:data-race|A@a.cpp", 1) for _ in range(7)]
    runs += [_run("timeout", "timeout", 0) for _ in range(3)]
    decision = decide(runs, 8, "tsan")
    assert not decision.accepted
    assert "< k=8" in decision.reason


def test_split_signatures_are_rejected():
    runs = [_run("tsan:data-race", "tsan:data-race|A@a.cpp", 1) for _ in range(5)]
    runs += [_run("tsan:data-race", "tsan:data-race|B@b.cpp", 1) for _ in range(3)]
    runs += [_run("none", "none", 0) for _ in range(2)]
    decision = decide(runs, 8, "tsan")
    assert not decision.accepted
    assert decision.count == 5


def test_timeouts_are_rejected():
    runs = [_run("timeout", "timeout", 0) for _ in range(10)]
    decision = decide(runs, 8, "tsan")
    assert not decision.accepted
    assert decision.signature is None


def test_tsan_without_app_frames_is_rejected():
    runs = [_run("tsan:data-race", "tsan:data-race", 0) for _ in range(10)]
    decision = decide(runs, 8, "tsan")
    assert not decision.accepted


def test_assertion_without_app_frames_is_accepted():
    runs = [_run("assert", "assert|a.cpp:1", 0) for _ in range(10)]
    decision = decide(runs, 8, "assertion")
    assert decision.accepted
    assert decision.signature == "assert|a.cpp:1"


def test_asan_is_not_eligible_for_tsan():
    runs = [_run("asan:heap-buffer-overflow", "asan:heap-buffer-overflow|f@a.cpp", 1) for _ in range(10)]
    decision = decide(runs, 8, "tsan")
    assert not decision.accepted
    assert decision.signature is None
