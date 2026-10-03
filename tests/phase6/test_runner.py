"""Resume must preserve the single attempt and write only complete JSON files."""
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from proofsmith.eval import runner
from proofsmith.eval.protocol import fingerprint
from proofsmith.ledger import BudgetExceeded


@pytest.fixture
def experiment(tmp_path, monkeypatch):
    protocol = {"id": "test", "model": "fake", "budget": {"max_steps": 2, "max_total_tokens": 100, "max_wall_s": 1},
        "tracks": {"B": ["one"]}, "pilot": {"B": ["one"]},
        "order": [{"track": "B", "instance_id": "one", "system": s} for s in runner.SYSTEMS]}
    path = tmp_path / "protocol.json"
    path.write_text(json.dumps(protocol))
    monkeypatch.setattr(runner.config, "RESULTS", tmp_path / "results")
    monkeypatch.setattr(runner, "LEDGER_PATH", tmp_path / "ledger.jsonl")
    monkeypatch.setattr(runner, "validate_protocol", lambda p: None)
    monkeypatch.setattr(runner, "load_case", lambda t, n: (SimpleNamespace(issue=SimpleNamespace(mentions_fix=False)), None))
    monkeypatch.setattr(runner, "load_bundle", lambda p: json.loads((p / "verifier.json").read_text()))
    calls = []

    def generate(system, instance, client, budget, dest):
        calls.append(system)
        dest.mkdir(parents=True)
        (dest / "verifier.json").write_text(json.dumps({"system": system}))

    def evaluate(bundle, *args):
        value = runner._error(protocol["order"][runner.SYSTEMS.index(bundle.name)], "recorded test error", 0)
        return SimpleNamespace(as_dict=lambda: value)

    monkeypatch.setattr(runner, "run_system", generate)
    monkeypatch.setattr(runner, "evaluate", evaluate)
    return protocol, path, calls


def run(path):
    return runner.run_eval(pilot=True, protocol_path=path, client_factory=lambda *a: SimpleNamespace())


def test_resume_does_not_repeat_observations(experiment):
    protocol, path, calls = experiment
    runner.run_eval(pilot=True, systems=["b0", "b1"], protocol_path=path, client_factory=lambda *a: SimpleNamespace())
    assert calls == ["b0", "b1"]
    assert run(path)["complete"]
    assert calls == list(runner.SYSTEMS)
    run(path)
    assert calls == list(runner.SYSTEMS)
    assert len(runner.read_rows(protocol)) == 3


def test_spending_cap_writes_no_partial_verdict(experiment, monkeypatch):
    protocol, path, calls = experiment
    monkeypatch.setattr(runner.Ledger, "ensure_budget", lambda self: (_ for _ in ()).throw(BudgetExceeded("cap")))
    with pytest.raises(BudgetExceeded):
        run(path)
    assert calls == []
    assert runner.read_rows(protocol) == []
    assert not list(runner.config.RESULTS.rglob("*.tmp"))
    assert not json.loads((runner.config.RESULTS / "summary.json").read_text())["complete"]


def test_interrupted_generation_is_not_silently_repeated(experiment, monkeypatch):
    protocol, path, calls = experiment

    def interrupt(*args):
        raise KeyboardInterrupt()

    monkeypatch.setattr(runner, "run_system", interrupt)
    with pytest.raises(KeyboardInterrupt):
        run(path)
    monkeypatch.setattr(runner, "run_system", lambda *a: pytest.fail("must not regenerate interrupted attempt"))
    runner.run_eval(pilot=True, systems=["b0"], protocol_path=path, client_factory=lambda *a: SimpleNamespace())
    rows = runner.read_rows(protocol)
    assert len(rows) == 1
    assert "interrupted" in rows[0]["error"]


def test_protocol_mismatch_rejected(experiment):
    protocol, path, _ = experiment
    run(path)
    dest = runner.result_root(protocol) / "B/one/b0.json"
    row = json.loads(dest.read_text())
    row["protocol_sha256"] = "different"
    dest.write_text(json.dumps(row))
    with pytest.raises(RuntimeError, match="protocol mismatch"):
        run(path)


def test_full_evaluation_requires_recorded_approval(experiment, monkeypatch, tmp_path):
    _, path, calls = experiment
    monkeypatch.setattr(runner.config, "REPO", tmp_path)
    with pytest.raises(RuntimeError, match="human budget approval"):
        runner.run_eval(protocol_path=path)
    assert not calls
