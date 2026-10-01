"""Phase 0 toolchain doctor. Builds real probes under ~/psw."""

from __future__ import annotations

import json

import pytest

from proofsmith.config import REPO, RESULTS
from proofsmith.toolchain import doctor, write_toolchain_json

pytestmark = pytest.mark.slow

NEEDLES = {
    "heap_overflow": "ERROR: AddressSanitizer",
    "use_after_free": "ERROR: AddressSanitizer",
    "signed_overflow": "runtime error:",
    "data_race": "WARNING: ThreadSanitizer",
    "lock_order": "WARNING: ThreadSanitizer",
    "check_fail": "PROOFSMITH_CHECK_FAILED",
}


def test_doctor_probes():
    results = doctor()
    write_toolchain_json(results)
    assert [item.name for item in results] == list(NEEDLES)
    for item in results:
        path = REPO / item.output_path
        text = path.read_text(encoding="utf-8")
        assert path.is_file()
        assert len(text.encode("utf-8")) > 200, f"{item.name} fixture is {len(text.encode('utf-8'))} bytes"
        assert NEEDLES[item.name] in text
        assert "/psw/probes/" in text, text[:500]
        assert "/mnt/c/" not in text
        assert item.ok, f"{item.name}: observed {item.observed_kind}\n{text[:2000]}"
        assert item.observed_kind == item.expected_kind
    lock = (REPO / "tests/fixtures/sanitizer/lock_order.txt").read_text(encoding="utf-8")
    assert "lock-order-inversion" in lock
    payload = json.loads((RESULTS / "toolchain.json").read_text(encoding="utf-8"))
    assert "clang version 18" in payload["clang_version"]
    assert len(payload["probes"]) == 6
