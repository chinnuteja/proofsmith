"""Offline development example on pinned upstream source; excluded from model evaluation."""
import json
import shutil
import subprocess
import tempfile
from datetime import datetime, timezone
from pathlib import Path

from proofsmith import config
from proofsmith.datasets.schema import Instance, apply_patch, materialize
from proofsmith.datasets.mine import mirror_path
from proofsmith.gate import check_patch, seal


def run_demo(out: Path | None = None) -> Path:
    instance = Instance.model_validate_json((config.REPO / "data/trackA/instances/Catch2-2288.json").read_text())
    mirror = mirror_path(instance.source.url)
    # The demo never fetches. Use the pinned source already cached by dataset preparation.
    if not mirror.is_dir() or subprocess.run(["git", "-C", str(mirror), "cat-file", "-e",
                                               instance.source.commit + "^{commit}"], capture_output=True).returncode:
        raise RuntimeError("Pinned Catch2 source is not cached; prepare the dataset before this offline demo")
    if out is None:
        out = config.RESULTS / "upstream-demo" / datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    out.mkdir(parents=True, exist_ok=False)
    config.WORK.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="upstream-demo-", dir=config.WORK) as directory:
        root = Path(directory)
        baseline = materialize(instance, root / "original")
        print("Qualifying supplied const API check on pinned Catch2 source", flush=True)
        qualification = seal(baseline, config.REPO / "examples/catch2-const-api", instance.build,
                             "assertion", out / "qualification")
        if qualification["status"] != "VERIFIED":
            raise RuntimeError("upstream check did not qualify; inspect qualification evidence")
        candidate = root / "candidate"
        shutil.copytree(baseline, candidate)
        # Only now, after the verifier is frozen, materialize the recorded upstream fix.
        apply_patch(candidate, config.REPO / "data/trackA/hidden/Catch2-2288.fix.diff")
        result = check_patch(out / "qualification/bundle", baseline, candidate, instance.build,
                             out / "fixed", qualification["bundle_id"])
        if result["status"] != "VERIFIED":
            raise RuntimeError("upstream fix did not pass; inspect saved evidence")
    summary = {"schema": "proofsmith.upstream-tool-demo/1", "instance_id": instance.id,
               "source_url": instance.source.url, "source_commit": instance.source.commit,
               "issue_url": instance.issue.url, "mode": "supplied development check; no model calls; outside comparative scores",
               "check": "Whether a const Approx factory is callable with a double, tested through its source header",
               "coverage_limit": "Type-level API check; does not establish runtime changed-function coverage",
               "bundle_id": qualification["bundle_id"], "baseline_target_failures": result["baseline"]["target_failures"],
               "candidate_target_failures": result["candidate"]["target_failures"], "n": result["policy"]["n"],
               "status": result["status"], "report": "fixed/index.html"}
    (out / "summary.json").write_text(json.dumps(summary, indent=2) + "\n")
    return out
