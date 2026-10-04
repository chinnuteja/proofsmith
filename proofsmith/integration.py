"""Run ByteAsk on a separate candidate and gate it with a pre-patch supplied check."""
from __future__ import annotations

import json
import os
import signal
import shutil
import subprocess
from pathlib import Path

from proofsmith.datasets.schema import Instance
from proofsmith.eval.runner import atomic_json
from proofsmith.freeze import TamperError, load_bundle
from proofsmith.gate import _copy_source, _output, bundle_id, check_patch
from proofsmith.mcp_server import local_instance
from proofsmith.oracles.builds import snapshot_sha256


def gated_run(bundle: Path, task: str, repo: Path, out: Path, expected_bundle_id: str,
              instance_path: Path | None = None, executable: str = "byteask",
              timeout_s: int = 1800, model: str | None = None, max_turns: int = 30) -> int:
    """No Proofsmith generator or DeepSeek client is created here.

    ByteAsk account usage is separate. A patcher completion never substitutes
    for an independently reproduced gate. The original checkout stays untouched.
    """
    work = _output(out, [bundle, repo])
    record = {"schema": "proofsmith.byteask-gate/1", "status": "INCONCLUSIVE", "exit_code": 2,
              "expected_bundle_id": expected_bundle_id, "model_requested": model,
              "candidate_path": str(work / "candidate"), "proofsmith_model_calls": 0}
    try:
        if not task.strip() or timeout_s < 1 or max_turns < 1:
            raise ValueError("provide a nonempty task and positive timeout and turn limits")
        if not shutil.which("bwrap"):
            raise RuntimeError("bubblewrap is required before launching the patcher")
        if bundle_id(bundle) != expected_bundle_id:
            raise TamperError("bundle differs from the identity retained before patching")
        meta = load_bundle(bundle)
        recipe = (Instance.model_validate_json(instance_path.read_text()).build if instance_path else
                  local_instance(repo, "ByteAsk supplied-check gate", task).build)
        if meta.get("status") not in {"accepted", "submitted"} or not meta.get("signature"):
            raise ValueError("supply a qualified frozen check")
        if meta.get("gate_recipe") is not None and meta["gate_recipe"] != recipe.model_dump():
            raise ValueError("build recipe differs from the qualified recipe")
        original = _copy_source(repo, work / "baseline")
        if original != meta.get("buggy_tree_sha256"):
            raise ValueError("original source differs from the frozen baseline")
        # Baseline and frozen bundle are outside the patcher's workspace-write cwd.
        (work / "frozen").mkdir()
        shutil.copyfile(bundle / "verifier.json", work / "frozen/verifier.json")
        shutil.copytree(bundle / "harness", work / "frozen/harness")
        if bundle_id(work / "frozen") != expected_bundle_id:
            raise TamperError("bundle changed during copying")
        if _copy_source(repo, work / "candidate") != original:
            raise ValueError("source changed while preparing the candidate")
        command = [executable, "exec", "--json", "--ephemeral", "--sandbox", "workspace-write",
                   "--skip-git-repo-check", "--color", "never", "--max-turns", str(max_turns)]
        if model:
            command += ["--model", model]
        command += ["-"]
        with (work / "byteask.jsonl").open("w") as stdout, (work / "byteask.stderr").open("w") as stderr:
            process = subprocess.Popen(command, cwd=work / "candidate", stdin=subprocess.PIPE, text=True,
                                       stdout=stdout, stderr=stderr, start_new_session=True)
            try:
                process.communicate(task, timeout=timeout_s)
            except subprocess.TimeoutExpired:
                # Stop the CLI's MCP/shell children as well as the CLI itself.
                os.killpg(process.pid, signal.SIGTERM)
                try:
                    process.communicate(timeout=5)
                except subprocess.TimeoutExpired:
                    os.killpg(process.pid, signal.SIGKILL)
                    process.communicate()
                raise
        record["patcher_exit_code"] = process.returncode
        if process.returncode:
            record.update(status="PATCHER_ERROR", reason=f"ByteAsk exited {process.returncode}; candidate not approved")
        elif snapshot_sha256(repo) != original or snapshot_sha256(work / "baseline") != original:
            record["reason"] = "Original source changed while ByteAsk was running"
        else:
            receipt = check_patch(work / "frozen", work / "baseline", work / "candidate", recipe,
                                  work / "evidence", expected_bundle_id)
            record.update(status=receipt["status"], exit_code=receipt["exit_code"], reason=receipt["reason"],
                          receipt_path=str(work / "evidence/receipt.json"), report_path=str(work / "evidence/index.html"),
                          baseline_sha256=receipt.get("baseline_sha256"), candidate_sha256=receipt.get("candidate_sha256"))
    except (ValueError, OSError, RuntimeError, TamperError, subprocess.TimeoutExpired) as exc:
        record.update(status="INCONCLUSIVE", reason=f"{type(exc).__name__}: {exc}")
    atomic_json(work / "gate.json", record)
    print(json.dumps(record, indent=2))
    return record["exit_code"]
