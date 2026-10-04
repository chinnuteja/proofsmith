"""Exercise patcher exit handling and frozen checks with an explicit local stub."""
import json
import shutil

import pytest

from proofsmith import config, integration
from proofsmith.gate import seal, bundle_id, check_receipt
from proofsmith.datasets.schema import BuildRecipe
from proofsmith.oracles.builds import snapshot_sha256


@pytest.fixture(scope="module")
def supplied_check(tmp_path_factory):
    out = tmp_path_factory.mktemp("sealed") / "qualification"
    result = seal(config.REPO / "examples/ci-smoke/original", config.REPO / "examples/ci-smoke/harness",
                  BuildRecipe(system="cmake"), "assertion", out)
    assert result["status"] == "VERIFIED", result
    return out / "bundle"


@pytest.mark.slow
@pytest.mark.timeout(300)
@pytest.mark.parametrize("action,expected", [("fix", 0), ("unchanged", 1), ("error", 2)])
def test_headless_gate_checks_patched_tree(tmp_path, monkeypatch, action, expected, supplied_check):
    repo = tmp_path / "repo"
    shutil.copytree(config.REPO / "examples/ci-smoke/original", repo)
    original = snapshot_sha256(repo)
    tools = tmp_path / "bin"
    tools.mkdir()
    command = "printf 'int total(int a, int b) { return a + b; }\\n' > calculation.cpp" if action == "fix" else "exit 7" if action == "error" else ":"
    patcher = tools / "byteask"
    patcher.write_text("#!/usr/bin/env bash\nset -eu\n[[ $1 == exec && $2 == --json && $5 == workspace-write ]]\n[[ $(cat) == repair ]]\n" + command + "\n")
    patcher.chmod(0o755)
    out = tmp_path / "run"
    assert integration.gated_run(supplied_check, "repair", repo, out, bundle_id(supplied_check),
                                 instance_path=config.REPO / "examples/ci-smoke/instance.json", executable=str(patcher)) == expected
    record = json.loads((out / "gate.json").read_text())
    assert record["status"] == {0: "VERIFIED", 1: "REJECTED", 2: "PATCHER_ERROR"}[expected]
    assert snapshot_sha256(repo) == original
    assert record["proofsmith_model_calls"] == 0
    if expected != 2:
        receipt = json.loads((out / "evidence/receipt.json").read_text())
        assert receipt["baseline"]["target_failures"] == 20
        assert receipt["candidate"]["fails"] == (0 if action == "fix" else 20)
        assert check_receipt(out / "evidence")["matches"]


def test_identity_mismatch_never_calls_patcher(tmp_path, monkeypatch, supplied_check):
    monkeypatch.setattr(integration.subprocess, "Popen", lambda *a, **k: pytest.fail("patcher must not start"))
    assert integration.gated_run(supplied_check, "repair", config.REPO / "examples/ci-smoke/original",
                                 tmp_path / "run", "untrusted") == 2


def test_timeout_cannot_approve_a_candidate(tmp_path, supplied_check):
    patcher = tmp_path / "patcher"
    patcher.write_text("#!/usr/bin/env bash\nsleep 60\n")
    patcher.chmod(0o755)
    repo = config.REPO / "examples/ci-smoke/original"
    before = snapshot_sha256(repo)
    out = tmp_path / "timed-out"
    assert integration.gated_run(supplied_check, "repair", repo, out, bundle_id(supplied_check),
                                 instance_path=config.REPO / "examples/ci-smoke/instance.json",
                                 executable=str(patcher), timeout_s=1) == 2
    assert "TimeoutExpired" in json.loads((out / "gate.json").read_text())["reason"]
    assert snapshot_sha256(repo) == before
