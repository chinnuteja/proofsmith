"""Protect against claiming wins from incomplete, scripted or abstain-only runs."""
import sys
from pathlib import Path
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))
from byteask_comparison import metrics
from byteask_comparison_cases import CASE_IDS


def rows(bad_ids=(), held_ids=(), origin="byteask_model"):
    return [{"case_id": case_id, "origin": origin,
             "judge_status": "INCORRECT" if case_id in bad_ids else "CORRECT_ON_JUDGE",
             "byteask_accepted": True, "augmented_accepted": case_id not in held_ids}
            for case_id in CASE_IDS]


def test_missing_case_cannot_be_reported_as_a_win():
    result = metrics(rows(bad_ids=CASE_IDS[:1], held_ids=CASE_IDS[:1])[:-1])
    assert not result["complete"] and not result["positive_pilot_signal"]


def test_scripted_controls_cannot_be_reported_as_a_model_win():
    result = metrics(rows(bad_ids=CASE_IDS[:1], held_ids=CASE_IDS[:1], origin="authored_control"))
    assert not result["valid_for_pilot_claim"] and not result["positive_pilot_signal"]


def test_rejecting_every_candidate_cannot_be_reported_as_a_win():
    result = metrics(rows(bad_ids=CASE_IDS, held_ids=CASE_IDS))
    assert result["complete"] and not result["positive_pilot_signal"]


def test_all_correct_baseline_means_no_demonstrated_advantage():
    result = metrics(rows())
    assert result["valid_for_pilot_claim"] and result["claim"] == "no demonstrated advantage"


def test_reducing_false_accepts_while_losing_good_fix_is_not_a_win():
    result = metrics(rows(bad_ids=CASE_IDS[:1], held_ids=CASE_IDS[:2]))
    assert not result["positive_pilot_signal"]


def test_reduced_false_accepts_and_retained_good_fixes_is_only_a_pilot_signal():
    result = metrics(rows(bad_ids=CASE_IDS[:1], held_ids=CASE_IDS[:1]))
    assert result["positive_pilot_signal"]
    assert "held-out confirmation required" in result["claim"]


def test_duplicate_case_is_rejected():
    items = rows()
    items[-1] = items[0]
    with pytest.raises(ValueError, match="duplicate"):
        metrics(items)


def test_unresolved_judge_blocks_a_win_claim():
    items = rows(bad_ids=CASE_IDS[:1], held_ids=CASE_IDS[:1])
    items[-1]["judge_status"] = "UNRESOLVED"
    assert not metrics(items)["positive_pilot_signal"]
