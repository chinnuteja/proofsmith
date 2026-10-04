"""Gate policy must fail closed on tampering, unrelated failures, and weak reproduction."""
import json
from pathlib import Path

import pytest

from proofsmith import config
from proofsmith.datasets.schema import BuildRecipe
from proofsmith.freeze import TamperError, VerifyResult, freeze
from proofsmith.gate import bundle_id, check_patch, check_receipt
from proofsmith.oracles.runner import RunResult
from proofsmith.oracles.signature import Evidence, Frame

RECIPE = BuildRecipe(system="cmake")
SIGNATURE = "asan:heap-use-after-free|read@source.cpp"


def setup_inputs(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "WORK", tmp_path / "work")
    baseline = tmp_path / "baseline"
    baseline.mkdir()
    (baseline / "source.cpp").write_text("original\n")
    harness = baseline / "proofsmith_harness"
    harness.mkdir()
    (harness / "build.sh").write_text("exit 0\n")
    bundle = freeze(baseline, {"status": "accepted", "oracle": "asan_ubsan", "variant": "asan_ubsan",
                              "signature": SIGNATURE, "gate_recipe": RECIPE.model_dump()}, tmp_path / "bundle")
    candidate = tmp_path / "candidate"
    candidate.mkdir()
    (candidate / "source.cpp").write_text("fixed\n")
    return bundle, baseline, candidate


def replay_stub(monkeypatch, baseline_fails=20, candidate_fails=0, kind="asan:heap-use-after-free", build_ok=True):
    def replay(bundle, repo, recipe, n, work):
        import shutil
        shutil.copytree(bundle / "harness", repo / "proofsmith_harness")
        work.mkdir(parents=True)
        log_dir = work / "logs"
        log_dir.mkdir()
        fails = baseline_fails if repo.name == "baseline" else candidate_fails
        runs = []
        if not build_ok:
            (work / "build.log").write_text("compiler failed\n")
            return VerifyResult(False, 0, n, [])
        for i in range(n):
            fail = i < fails
            run_kind = kind if fail else "none"
            signature = SIGNATURE if fail and kind.startswith("asan:") else run_kind
            path = log_dir / f"run-{i:02d}.log"
            path.write_text("<script>alert('unescaped')</script>" if fail else "")
            frame = Frame(0, "read", str(repo / "source.cpp"), 3)
            evidence = Evidence(run_kind, [frame] if fail else [], [frame] if fail else [], signature)
            runs.append(RunResult(i, 1 if fail else 0, False, 0.01, evidence, str(path)))
        return VerifyResult(True, fails, n, runs)
    monkeypatch.setattr("proofsmith.gate.verify_bundle", replay)


@pytest.mark.parametrize("baseline_fails,candidate_fails,kind,status", [
    (20, 0, "asan:heap-use-after-free", "VERIFIED"),
    (20, 1, "asan:heap-use-after-free", "REJECTED"),
    (15, 0, "asan:heap-use-after-free", "INCONCLUSIVE"),
    (20, 0, "crash:SIGSEGV", "INCONCLUSIVE"),
])
def test_policy_and_portable_evidence(tmp_path, monkeypatch, baseline_fails, candidate_fails, kind, status):
    bundle, baseline, candidate = setup_inputs(tmp_path, monkeypatch)
    replay_stub(monkeypatch, baseline_fails, candidate_fails, kind)
    out = tmp_path / "evidence"
    result = check_patch(bundle, baseline, candidate, RECIPE, out, bundle_id(bundle))
    assert result["status"] == status
    assert result["exit_code"] == {"VERIFIED": 0, "REJECTED": 1, "INCONCLUSIVE": 2}[status]
    assert (candidate / "source.cpp").read_text() == "fixed\n"
    assert not (candidate / "proofsmith_harness").exists()
    assert check_receipt(out)["matches"]
    assert "<script>" not in (out / "index.html").read_text()


def test_metadata_tamper_is_detected_with_pinned_identity(tmp_path, monkeypatch):
    bundle, baseline, candidate = setup_inputs(tmp_path, monkeypatch)
    identity = bundle_id(bundle)
    meta = json.loads((bundle / "verifier.json").read_text())
    meta["signature"] = "different target"
    (bundle / "verifier.json").write_text(json.dumps(meta))
    monkeypatch.setattr("proofsmith.gate.verify_bundle", lambda *args: pytest.fail("tampered bundle executed"))
    result = check_patch(bundle, baseline, candidate, RECIPE, tmp_path / "evidence", identity)
    assert result["status"] == "INCONCLUSIVE"
    assert "identity" in result["reason"]


def test_changed_baseline_cannot_pass(tmp_path, monkeypatch):
    bundle, baseline, candidate = setup_inputs(tmp_path, monkeypatch)
    (baseline / "source.cpp").write_text("already patched")
    monkeypatch.setattr("proofsmith.gate.verify_bundle", lambda *args: pytest.fail("changed baseline executed"))
    result = check_patch(bundle, baseline, candidate, RECIPE, tmp_path / "evidence", bundle_id(bundle))
    assert result["status"] == "INCONCLUSIVE"
    assert "baseline" in result["reason"]


def test_build_failure_has_receipt_and_log(tmp_path, monkeypatch):
    bundle, baseline, candidate = setup_inputs(tmp_path, monkeypatch)
    replay_stub(monkeypatch, build_ok=False)
    out = tmp_path / "evidence"
    result = check_patch(bundle, baseline, candidate, RECIPE, out, bundle_id(bundle))
    assert result["status"] == "INCONCLUSIVE"
    assert (out / "evidence/baseline/build.log").read_text() == "compiler failed\n"
    assert check_receipt(out)["matches"]


def test_evidence_tamper_and_extra_file_detected(tmp_path, monkeypatch):
    bundle, baseline, candidate = setup_inputs(tmp_path, monkeypatch)
    replay_stub(monkeypatch)
    out = tmp_path / "evidence"
    check_patch(bundle, baseline, candidate, RECIPE, out, bundle_id(bundle))
    (out / "extra.txt").write_text("new")
    with pytest.raises(TamperError):
        check_receipt(out)
    (out / "extra.txt").unlink()
    (out / "evidence/baseline/logs/run-00.log").write_text("changed")
    with pytest.raises(TamperError):
        check_receipt(out)


def test_changed_recipe_and_symlink_cannot_pass(tmp_path, monkeypatch):
    bundle, baseline, candidate = setup_inputs(tmp_path, monkeypatch)
    changed = RECIPE.model_copy(update={"cmake_args": ["-DSANITIZERS=OFF"]})
    result = check_patch(bundle, baseline, candidate, changed, tmp_path / "changed-recipe", bundle_id(bundle))
    assert result["status"] == "INCONCLUSIVE" and "recipe" in result["reason"]
    (candidate / "outside.cpp").symlink_to(baseline / "source.cpp")
    result = check_patch(bundle, baseline, candidate, RECIPE, tmp_path / "symlink", bundle_id(bundle))
    assert result["status"] == "INCONCLUSIVE" and "symlink" in result["reason"]


def test_never_overwrite_source_or_existing_receipt(tmp_path, monkeypatch):
    bundle, baseline, candidate = setup_inputs(tmp_path, monkeypatch)
    with pytest.raises(ValueError):
        check_patch(bundle, baseline, candidate, RECIPE, candidate / "evidence")
    out = tmp_path / "existing"
    out.mkdir()
    with pytest.raises(FileExistsError):
        check_patch(bundle, baseline, candidate, RECIPE, out)


def test_unpinned_check_never_passes(tmp_path, monkeypatch):
    bundle, baseline, candidate = setup_inputs(tmp_path, monkeypatch)
    monkeypatch.setattr("proofsmith.gate.verify_bundle", lambda *args: pytest.fail("unpinned check executed"))
    result = check_patch(bundle, baseline, candidate, RECIPE, tmp_path / "evidence")
    assert result["status"] == "INCONCLUSIVE" and "trusted" in result["reason"]


def test_check_cannot_rewrite_application_source(tmp_path, monkeypatch):
    bundle, baseline, candidate = setup_inputs(tmp_path, monkeypatch)
    replay_stub(monkeypatch)
    from proofsmith import gate
    replay = gate.verify_bundle
    def corrupt(*args):
        result = replay(*args)
        (args[1] / "source.cpp").write_text("silently patched by the harness")
        return result
    monkeypatch.setattr(gate, "verify_bundle", corrupt)
    result = check_patch(bundle, baseline, candidate, RECIPE, tmp_path / "evidence", bundle_id(bundle))
    assert result["status"] == "INCONCLUSIVE" and "changed the source" in result["reason"]


def test_replaced_manifest_is_detected_with_trusted_digest(tmp_path, monkeypatch):
    bundle, baseline, candidate = setup_inputs(tmp_path, monkeypatch)
    replay_stub(monkeypatch)
    out = tmp_path / "evidence"
    check_patch(bundle, baseline, candidate, RECIPE, out, bundle_id(bundle))
    trusted = check_receipt(out)["manifest_sha256"]
    manifest = json.loads((out / "manifest.json").read_text())
    (out / "manifest.json").write_text(json.dumps(manifest))
    with pytest.raises(TamperError):
        check_receipt(out, trusted)


def test_cli_invalid_policy_is_inconclusive(tmp_path, monkeypatch, capsys):
    from proofsmith.cli import main
    bundle, baseline, candidate = setup_inputs(tmp_path, monkeypatch)
    instance = tmp_path / "instance.json"
    instance.write_text(json.dumps({"schema": "proofsmith.instance/1", "id": "cli", "track": "micro",
                                  "source": {"kind": "dir", "path": str(baseline)},
                                  "issue": {"title": "CLI", "body": ""}, "build": RECIPE.model_dump()}))
    with pytest.raises(SystemExit) as stopped:
        main(["gate", "--bundle", str(bundle), "--baseline", str(baseline), "--candidate", str(candidate),
              "--instance", str(instance), "--expect-bundle-id", bundle_id(bundle),
              "--n", "1", "--out", str(tmp_path / "evidence")])
    assert stopped.value.code == 2
    assert json.loads(capsys.readouterr().out)["status"] == "INCONCLUSIVE"


@pytest.mark.slow
@pytest.mark.timeout(240)
def test_real_reference_gate_demo(tmp_path, monkeypatch):
    from proofsmith.gate_demo import run_demo
    # A real compiler + TSan run; no model response can supply the expected outcome.
    monkeypatch.setenv("DEEPSEEK_API_KEY", "")
    out = run_demo(tmp_path / "demo")
    summary = json.loads((out / "summary.json").read_text())
    assert [r["status"] for r in summary["rows"]] == ["REJECTED", "VERIFIED", "VERIFIED"]
    assert all(r["existing_tests_exit_code"] == 0 for r in summary["rows"])
    assert all(r["baseline_target_failures"] >= 16 for r in summary["rows"])
    assert summary["rows"][0]["candidate_target_failures"] >= 16
    assert all(r["candidate_target_failures"] == 0 for r in summary["rows"][1:])
    import os
    import shutil
    if os.environ.get("PROOFSMITH_RECORD_TOOL_DEMO") == "1":
        shutil.copytree(out, config.RESULTS / "tool-demo/orderd", dirs_exist_ok=True)
