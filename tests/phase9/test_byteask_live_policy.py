"""The real-run collector must fail closed on usage and ambiguous acceptance."""
import sys
from pathlib import Path
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))
from byteask_comparison_live import marker, quota_guard


def allowance(**changes):
    return {"plan": "pro", "extra_balance_usd": 0, "extra_spent_usd": 0,
            "used_5h_pct": 0, "used_week_pct": 0, **changes}


@pytest.mark.parametrize("changes", [
    {"extra_balance_usd": 10}, {"extra_spent_usd": 0.01},
    {"used_5h_pct": 80}, {"used_week_pct": None}, {"plan": "unknown"},
])
def test_unknown_or_extra_credit_usage_cannot_start_a_model_run(changes):
    with pytest.raises(RuntimeError):
        quota_guard(allowance(**changes))


def test_existing_allowance_without_extra_credit_is_allowed():
    quota_guard(allowance())


@pytest.mark.parametrize("response", [
    "No fix available.", "Example: BYTEASK_ACCEPTED\nStill investigating.",
    "BYTEASK_ACCEPTED\nBYTEASK_UNRESOLVED", "BYTEASK_UNRESOLVED\nBYTEASK_ACCEPTED",
])
def test_ambiguous_or_nonfinal_acceptance_is_unresolved(response):
    assert marker(response) == "UNRESOLVED"


def test_only_a_single_final_acceptance_marker_is_accepted():
    assert marker("Fixed it and ran the supplied regression.\nBYTEASK_ACCEPTED\n") == "ACCEPTED"
