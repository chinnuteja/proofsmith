"""Exercise patcher exit handling and frozen checks with an explicit local stub."""
import json
import os
import shlex
import shutil
from types import SimpleNamespace

import pytest

from proofsmith import config, integration


@pytest.mark.slow
@pytest.mark.timeout(300)
@pytest.mark.parametrize("action,expected", [("fix", 0), ("unchanged", 1), ("error", 2)])
def test_headless_gate_checks_patched_tree(tmp_path, monkeypatch, action, expected):
    repo = tmp_path / "repo"
    shutil.copytree(config.REPO / "cases/orderd/buggy", repo)
    bundle = config.RESULTS / "verifiers/orderd-deadlock/bundle"
    monkeypatch.setattr(integration, "make_verifier", lambda *args, **kwargs:
        SimpleNamespace(status="accepted", bundle_dir=bundle))
    monkeypatch.setattr(integration, "reference_client", lambda repo: object())
    monkeypatch.setenv("PROOFSMITH_FAKE_LLM", "reference")
    monkeypatch.setattr(config, "RESULTS", tmp_path / "results")
    tools = tmp_path / "bin"
    tools.mkdir()
    patch = config.REPO / "cases/orderd/variants/scoped_cancel.patch"
    command = f"patch -p1 < {shlex.quote(str(patch))}" if action == "fix" else "exit 7" if action == "error" else ":"
    patcher = tools / "byteask"
    patcher.write_text("#!/usr/bin/env bash\nset -eu\n[[ $1 == exec && $2 == repair ]]\n" + command + "\n")
    patcher.chmod(0o755)
    monkeypatch.setenv("PATH", str(tools) + os.pathsep + os.environ["PATH"])
    issue = tmp_path / "issue.json"
    issue.write_text(json.dumps({"title": "orderd deadlock", "body": "cancel and risk deadlock"}))
    assert integration.gated_run(issue, "repair", repo) == expected
    record = json.loads(next((config.RESULTS / "integration").glob("*/gate.json")).read_text())
    assert record["status"] == {0: "PASS", 1: "FAIL", 2: "PATCHER_ERROR"}[expected]
    if expected != 2:
        assert record["build_ok"] and record["reference_mode"]
        assert record["fails"] == (0 if action == "fix" else config.EVAL_N)
