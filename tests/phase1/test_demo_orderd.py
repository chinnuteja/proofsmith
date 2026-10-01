"""The orderd demo: tests stay green, the TSan check does not."""

from __future__ import annotations

import json
import re

import pytest

from proofsmith.config import REPO
from proofsmith.demo import run_orderd

pytestmark = [pytest.mark.slow, pytest.mark.timeout(1200)]

_FORBIDDEN = re.compile(r"\b(locks?|mutex(?:es)?|ordering|scoped_lock)\b", re.IGNORECASE)


def test_issue_is_symptoms_only():
    instance = json.loads((REPO / "cases" / "orderd" / "instance.json").read_text(encoding="utf-8"))
    text = instance["issue"]["title"] + "\n" + instance["issue"]["body"]
    assert _FORBIDDEN.search(text) is None, text
    assert instance["issue"]["mentions_fix"] is False


def test_demo_orderd_matrix():
    path = run_orderd()
    data = json.loads(path.read_text(encoding="utf-8"))
    for name in ("buggy", "timing_backoff", "scoped_cancel", "consistent_order"):
        assert data["rows"][name]["ctest"] == {"passed": 3, "total": 3}, name
    assert data["rows"]["buggy"]["verifier"]["fails"] >= 16
    assert data["rows"]["timing_backoff"]["verifier"]["fails"] >= 16
    assert data["rows"]["scoped_cancel"]["verifier"]["fails"] == 0
    assert data["rows"]["consistent_order"]["verifier"]["fails"] == 0
    assert data["rows"]["buggy"]["verifier"]["n"] == 20
    assert data["decision"]["accepted"] is True
    signature = data["verifier"]["signature"]
    assert "OrderBook::cancel" in signature or "OrderBook::risk_sweep" in signature, signature
    assert "lock-order-inversion" in data["raw_report_buggy"]
