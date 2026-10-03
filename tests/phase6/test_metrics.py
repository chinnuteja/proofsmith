import pytest

from proofsmith.eval.metrics import mcnemar, summarize, wilson


def row(name, system, success=False, track="B", **extra):
    return {"track": track, "instance_id": name, "system": system, "f2p": success,
        "alignment": {"strict": success, "relaxed": success, "unknown": False},
        "bundle_status": "submitted", "cost_usd": 1, "wall_s": 2, "fixed_fails": 0, "n": 20, **extra}


def test_wilson_and_mcnemar():
    assert wilson(0, 0) is None
    assert wilson(5, 10) == pytest.approx([0.2365930905, 0.7634069095])
    assert mcnemar(5, 0) == 0.0625
    assert mcnemar(3, 3) == 1


def test_exact_twenty_point_lift_passes():
    ids = [str(i) for i in range(5)]
    rows = [row(i, system, system == "proofsmith" and i == "0") for i in ids for system in ("b0", "b1", "proofsmith")]
    result = summarize(rows, {"B": ids})
    assert result["tracks"]["B"]["verdict"] == "PASS"
    rows[2]["f2p"] = False
    assert summarize(rows, {"B": ids})["tracks"]["B"]["verdict"] == "KILL_OR_RETHINK"


def test_missing_runs_are_incomplete_not_failures():
    result = summarize([row("a", "proofsmith", True)], {"B": ["a"]})
    assert not result["complete"]
    assert result["tracks"]["B"]["verdict"] == "INCOMPLETE"
    assert result["tracks"]["B"]["systems"]["b1"]["raw_f2p"]["pct"] is None


def test_alignment_unknown_prevents_kill_verdict():
    rows = [row("a", s, True) for s in ("b0", "b1", "proofsmith")]
    rows[0]["alignment"]["unknown"] = True
    assert summarize(rows, {"B": ["a"]})["tracks"]["B"]["verdict"] == "ALIGNMENT_UNRESOLVED"


def test_abstention_precision_requires_observed_baseline():
    rows = [row("a", "proofsmith", bundle_status="abstained"), row("b", "proofsmith", bundle_status="abstained"), row("a", "b1")]
    value = summarize(rows, {"B": ["a", "b"]})["tracks"]["B"]["abstention_precision"]
    assert value == {"total": 2, "paired": 1, "correct": 1, "value": 1}


def test_duplicate_verdicts_are_rejected():
    with pytest.raises(ValueError, match="duplicate"):
        summarize([row("a", "b1"), row("a", "b1")], {"B": ["a"]})
