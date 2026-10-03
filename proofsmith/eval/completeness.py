"""Release gate: complete means every protocol observation is present and current."""
import json

from proofsmith import config
from proofsmith.eval.protocol import PROTOCOL_PATH, fingerprint, validate_protocol
from proofsmith.eval.runner import read_rows, result_root


def check_complete() -> None:
    protocol = json.loads(PROTOCOL_PATH.read_text())
    validate_protocol(protocol)
    digest = fingerprint(protocol)
    summary_path = config.RESULTS / "summary.json"
    summary = json.loads(summary_path.read_text())
    rows = read_rows(protocol)
    expected = len(protocol["order"])
    if len(rows) != expected or not summary.get("complete"):
        raise RuntimeError(f"evaluation incomplete: {len(rows)}/{expected} observations")
    if summary.get("protocol_sha256") != digest:
        raise RuntimeError("summary protocol mismatch")
    from proofsmith.eval.metrics import summarize
    recomputed = summarize(rows, protocol["tracks"])
    if summary["tracks"] != recomputed["tracks"]:
        raise RuntimeError("summary does not match verdicts")
    for pair in protocol["order"]:
        path = result_root(protocol) / pair["track"] / pair["instance_id"] / f"{pair['system']}.json"
        if path.stat().st_mtime_ns > summary_path.stat().st_mtime_ns:
            raise RuntimeError(f"summary is older than {path}")
    pilot = json.loads((config.RESULTS / "pilot_cost.json").read_text())
    approval = json.loads((config.REPO / "docs/evaluation-approval.json").read_text())
    if not pilot["complete"] or pilot["protocol_sha256"] != digest or approval["protocol_sha256"] != digest:
        raise RuntimeError("pilot or recorded approval is missing or belongs to a different protocol")


if __name__ == "__main__":
    check_complete()
    print("evaluation completeness: PASS")
