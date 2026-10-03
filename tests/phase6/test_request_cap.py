from types import SimpleNamespace

import pytest

from proofsmith import ledger
from proofsmith.llm import LLMClient


def test_request_is_rejected_before_network_when_reservation_exceeds_cap(tmp_path, monkeypatch):
    monkeypatch.setattr(ledger, "MAX_USD", 0.01)
    client = object.__new__(LLMClient)
    client.model = "deepseek-v4-pro"
    client.ledger = ledger.Ledger(tmp_path / "ledger.jsonl")
    client.costs = []
    client.run_id = "must-not-send"
    client._client = SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(
        create=lambda **kwargs: pytest.fail("billable request must not be sent"))))
    with pytest.raises(ledger.BudgetExceeded, match="request upper bound"):
        client.chat([{"role": "user", "content": "hello"}], None, 16384)
    assert client.ledger.spent_usd() == 0
