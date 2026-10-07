"""Re-evaluate retained real candidates from a checkout or extracted kit, offline."""
from __future__ import annotations
import argparse
import json
from pathlib import Path
import tempfile
from byteask_comparison import ROOT, config, digest, score


def rescore(out: Path):
    live = ROOT / "experiments/byteask-comparison/live-v1"
    items = json.loads((live / "observations.json").read_text())
    lock_hash = digest(live / "execution-lock.json")
    for item in items:
        case = live / item["case_id"]
        trace = case / "byteask.jsonl"
        if digest(trace) != item["transcript_sha256"] or item["execution_lock_sha256"] != lock_hash:
            raise ValueError("retained live evidence changed")
        # Original collector records retain the original absolute paths. Rebase
        # only this temporary scoring input; never rewrite the collected record.
        item["candidate_path"] = str(case / "candidate")
        item["transcript_path"] = str(trace)
    config.WORK.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="byteask-rescore-", dir=config.WORK) as name:
        observations = Path(name) / "rebased-observations.json"
        observations.write_text(json.dumps(items))
        score(ROOT / "experiments/byteask-comparison/v1", observations, out)
    recorded = json.loads((ROOT / "experiments/byteask-comparison/live-v1-score/results.json").read_text())
    fresh = json.loads((out / "results.json").read_text())
    if recorded["metrics"] != fresh["metrics"]:
        raise ValueError("fresh candidate evaluation disagrees with the recorded metrics")
    for old, new in zip(recorded["rows"], fresh["rows"]):
        for key in ("case_id", "judge_status", "judge_checks", "gate_status", "byteask_accepted", "augmented_accepted"):
            if old[key] != new[key]:
                raise ValueError(f"fresh candidate evaluation disagrees: {old['case_id']}/{key}")
    print("Fresh independent evaluators and frozen gates reproduce the recorded live decisions.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, required=True, help="new output directory")
    args = parser.parse_args()
    rescore(args.out.resolve())
