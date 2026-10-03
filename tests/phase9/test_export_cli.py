import json
import os
import subprocess
import sys

from proofsmith.benchmark import export_benchmark


def test_export_cli_evaluates_without_original_source_path_or_key(tmp_path):
    dest = export_benchmark(tmp_path / "standalone")
    env = {k: v for k, v in os.environ.items() if k not in {"DEEPSEEK_API_KEY", "PYTHONPATH"}}
    command = [sys.executable, "-m", "proofsmith.cli", "evaluate",
        "--bundle", "results/eval/B/spdlog-1570/proofsmith",
        "--instance", "data/trackB/instances/spdlog-1570.json",
        "--hidden", "data/trackB/hidden/spdlog-1570.json", "--out", "verdict.json"]
    completed = subprocess.run(command, cwd=dest, env=env, capture_output=True, text=True, timeout=60)
    assert completed.returncode == 0, completed.stderr
    value = json.loads((dest / "verdict.json").read_text())
    assert value["instance_id"] == "spdlog-1570"
    assert value["bundle_status"] == "abstained" and not value["f2p"]
    origin = subprocess.run([sys.executable, "-c", "from proofsmith.config import REPO; print(REPO)"],
                            cwd=dest, env=env, capture_output=True, text=True, check=True)
    assert origin.stdout.strip() == str(dest)
