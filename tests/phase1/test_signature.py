"""Phase 1 evidence parser, checked against the Phase 0 fixtures."""

from __future__ import annotations

import re
from pathlib import Path

from proofsmith.config import REPO
from proofsmith.oracles.signature import normalize_function, parse_evidence

FIXTURES = REPO / "tests" / "fixtures" / "sanitizer"

EXPECTED = {
    "heap_overflow": "asan:heap-buffer-overflow",
    "use_after_free": "asan:heap-use-after-free",
    "signed_overflow": "ubsan:signed-integer-overflow",
    "data_race": "tsan:data-race",
    "lock_order": "tsan:lock-order-inversion",
    "check_fail": "assert",
}


def _read(name: str) -> str:
    return (FIXTURES / f"{name}.txt").read_text(encoding="utf-8")


def test_fixture_kinds():
    for name, kind in EXPECTED.items():
        evidence = parse_evidence(_read(name), 1, False, "/home/chinnu/psw/probes")
        assert evidence.kind == kind, name


def test_lock_order_signature_has_app_frame_and_no_addresses():
    text = _read("lock_order")
    found = re.search(r"(/[^\s:]+)/lock_order\.cpp", text)
    assert found, "fixture has no lock_order.cpp frame"
    repo_root = str(Path(found.group(1)))
    evidence = parse_evidence(text, 66, False, repo_root)
    assert evidence.app_frames
    assert evidence.signature.startswith("tsan:lock-order-inversion|")
    assert re.search(r"0x[0-9a-fA-F]+", evidence.signature) is None
    assert re.search(r":\d+", evidence.signature) is None


def test_assert_fixture_signature():
    text = _read("check_fail")
    found = re.search(r"PROOFSMITH_CHECK_FAILED (\S+):(\d+):", text)
    assert found
    repo_root = str(Path(found.group(1)).parent)
    evidence = parse_evidence(text, 134, False, repo_root)
    assert evidence.signature == f"assert|check_fail.cpp:{found.group(2)}"


def test_lambda_normalizes():
    assert normalize_function("main::$_3::operator()() const") == "main::$_::operator()"
    line = "    #0 main::$_3::operator()() const /repo/file.cpp:4:2 (bin+0x10)\n"
    evidence = parse_evidence("WARNING: ThreadSanitizer: data race (pid=1)\n" + line, 66, False, "/repo")
    assert evidence.app_frames
    assert normalize_function(evidence.app_frames[0].function) == "main::$_::operator()"
    assert "main::$_::operator()@file.cpp" in evidence.signature


def test_library_and_harness_frames_are_not_app_frames():
    text = "\n".join(
        [
            "WARNING: ThreadSanitizer: data race (pid=1)",
            "    #0 foo() /usr/include/x.h:1:1",
            "    #1 baz() /repo/proofsmith_harness/harness.cpp:3:1",
            "    #2 bar() /repo/src.cpp:2:1",
        ]
    )
    evidence = parse_evidence(text, 66, False, "/repo")
    files = [frame.file for frame in evidence.app_frames]
    assert files == ["/repo/src.cpp"]
    assert all(not frame.file.startswith("/usr/include") for frame in evidence.app_frames)
    assert all("proofsmith_harness" not in frame.file for frame in evidence.app_frames)


def test_timeout_and_sigsegv():
    timeout = parse_evidence("still running", 0, True, "/repo")
    assert timeout.kind == "timeout"
    assert timeout.signature == "timeout"
    crash = parse_evidence("Segmentation fault", 139, False, "/repo")
    assert crash.kind == "crash:SIGSEGV"
    assert crash.signature == "crash:SIGSEGV"
