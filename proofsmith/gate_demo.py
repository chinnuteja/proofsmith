"""One-command reference demo of the offline patch gate; never a model benchmark win."""
import json
import shutil
import subprocess
import tempfile
from datetime import datetime, timezone
from pathlib import Path

from proofsmith import config
from proofsmith.datasets.schema import Instance, apply_patch
from proofsmith.gate import check_patch, check_receipt, seal
from proofsmith.oracles.builds import build_variant


def run_demo(out: Path | None = None) -> Path:
    fixture = config.REPO / "cases/orderd"
    instance = Instance.model_validate_json((fixture / "instance.json").read_text())
    if out is None:
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
        out = config.RESULTS / "gate-demo" / stamp
    out.mkdir(parents=True, exist_ok=False)
    config.WORK.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="gate-demo-", dir=config.WORK) as directory:
        root = Path(directory)
        baseline = root / "original"
        shutil.copytree(fixture / "buggy", baseline)
        print("Qualifying hand-written reference check (no model calls)", flush=True)
        qualified = seal(baseline, fixture / "reference_harness", instance.build, "tsan", out / "qualification")
        if qualified["status"] != "VERIFIED":
            raise RuntimeError("reference check could not qualify; inspect the qualification receipt")
        rows = []
        for name in ("timing_backoff", "scoped_cancel", "consistent_order"):
            candidate = root / name
            shutil.copytree(fixture / "buggy", candidate)
            apply_patch(candidate, fixture / "variants" / (name + ".patch"))
            build = build_variant(candidate, "plain", instance.build, root / (name + "-build"))
            if not build.ok:
                raise RuntimeError(name + " plain build failed")
            # CTest may write into its build tree, so use a disposable cache copy.
            test_dir = root / (name + "-tests")
            shutil.copytree(build.build_dir, test_dir)
            tests = subprocess.run(["ctest", "--test-dir", str(test_dir), "--output-on-failure"],
                                   capture_output=True, text=True, check=False)
            print("Testing " + name + ": existing tests exit " + str(tests.returncode), flush=True)
            receipt = check_patch(out / "qualification/bundle", baseline, candidate, instance.build,
                                  out / name, qualified["bundle_id"])
            expected = "REJECTED" if name == "timing_backoff" else "VERIFIED"
            if tests.returncode or receipt["status"] != expected:
                raise RuntimeError(name + " demo outcome unexpected; inspect the saved evidence")
            (out / name / "existing-tests.log").write_text(tests.stdout + tests.stderr)
            # Add the independently run existing-test evidence to its manifest.
            from proofsmith.gate import _finish
            _finish(out / name, receipt)
            check_receipt(out / name)
            rows.append({"variant": name, "existing_tests_exit_code": tests.returncode,
                         "status": receipt["status"], "baseline_target_failures": receipt["baseline"]["target_failures"],
                         "candidate_target_failures": receipt["candidate"]["target_failures"], "n": receipt["policy"]["n"],
                         "report": name + "/index.html", "receipt": name + "/receipt.json"})
            print(name + ": " + receipt["status"], flush=True)
    summary = {"schema": "proofsmith.gate-demo/1", "mode": "controlled fixture; hand-written reference; no model calls",
               "bundle_id": qualified["bundle_id"], "rows": rows}
    (out / "summary.json").write_text(json.dumps(summary, indent=2) + "\n")
    from proofsmith.report.gate import render_demo
    render_demo(out, summary)
    return out
