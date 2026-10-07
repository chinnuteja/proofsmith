"""Render recorded live results; never run a model or change frozen inputs."""
from __future__ import annotations
import argparse
from html import escape
import json
import os
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
from byteask_comparison import ROOT, digest, validate
from proofsmith.gate import check_receipt


def render(live: Path, scored: Path):
    experiment = ROOT / "experiments/byteask-comparison/v1"
    validate(experiment)
    results = json.loads((scored / "results.json").read_text())
    collection = json.loads((live / "collection.json").read_text())
    lock = json.loads((live / "execution-lock.json").read_text())
    assert results["protocol_sha256"] == digest(experiment / "protocol.json") == lock["protocol_sha256"]
    metrics, rows = results["metrics"], results["rows"]
    assert metrics["observations"] == collection["observations"] == len(rows)
    report = scored / "index.html"

    def link(path: Path, label: str):
        relative = os.path.relpath(path, scored).replace(os.sep, "/")
        return f'<a href="{escape(relative, quote=True)}">{escape(label)}</a>'

    table, details = [], []
    for row in rows:
        case_id = row["case_id"]
        evidence = live / case_id
        assert digest(evidence / "byteask.jsonl") == row["transcript_sha256"]
        assert digest(live / "execution-lock.json") == row["execution_lock_sha256"]
        check_receipt(scored / case_id / "gate")
        receipt = json.loads((scored / case_id / "gate/receipt.json").read_text())
        table.append(f'<tr><th scope="row">{escape(case_id)}</th>'
                     f'<td>{"Accepted" if row["byteask_accepted"] else "Unresolved"}</td>'
                     f'<td>{escape(row["judge_status"])}</td>'
                     f'<td>{link(scored / case_id / "gate/index.html", row["gate_status"])}</td>'
                     f'<td>{"Accepted" if row["augmented_accepted"] else "Unresolved / refused"}</td>'
                     f'<td>{row["wall_s"]:.1f}s + {row["gate_wall_s"]:.1f}s</td></tr>')
        final = (evidence / "final.txt").read_text()
        details.append(f'<details><summary>{escape(case_id)}: inspect the evidence</summary>'
                       f'<p>Independent evaluator checks: {row["judge_checks"]}. '
                       f'Frozen gate failures: original {receipt.get("baseline", {}).get("fails", "unavailable")}/20, '
                       f'candidate {receipt.get("candidate", {}).get("fails", "unavailable")}/20.</p>'
                       f'<p>{link(evidence / "candidate.diff", "Candidate diff")} · '
                       f'{link(evidence / "byteask.jsonl", "ByteAsk transcript")} · '
                       f'{link(evidence / "byteask.stderr", "CLI stderr")} · '
                       f'{link(scored / case_id / "judge/result.json", "Independent judge result")} · '
                       f'{link(scored / case_id / "judge/run.log", "Judge output")}</p>'
                       f'<p>Collector note: {escape(row.get("reason") or "No execution error recorded")}</p>'
                       f'<pre>{escape(final or "No final response recorded.")}</pre></details>')
    last_usage = rows[-1]["account_usage"]["after"] if rows else None
    headline = "Gate catches mistakes in this five-case pilot" if metrics["positive_pilot_signal"] else (
        "Five repairs tested. No advantage demonstrated." if metrics["valid_for_pilot_claim"] else
        "Comparison incomplete. No win claim.")
    body = f'''<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Proofsmith: real ByteAsk comparison</title><style>
*{{box-sizing:border-box}}body{{margin:0;background:#101820;color:#e5edf5;font:16px system-ui;line-height:1.6}}main{{max-width:1120px;margin:auto;padding:32px 24px}}h1{{font-size:clamp(26px,4vw,40px);line-height:1.2}}a{{color:#8ecbff}}.label{{color:#a3bacd;font-size:13px;letter-spacing:.08em}}.cards{{display:grid;grid-template-columns:repeat(auto-fit,minmax(180px,1fr));gap:12px}}.card,details{{border:1px solid #344453;border-radius:8px;padding:16px;margin:12px 0}}.card strong{{display:block;font-size:28px}}.table{{overflow:auto}}table{{border-collapse:collapse;width:100%;font-size:14px}}th,td{{padding:12px;text-align:left;border-bottom:1px solid #344453}}pre{{white-space:pre-wrap;overflow-wrap:anywhere;font-size:13px}}code{{overflow-wrap:anywhere}}summary{{cursor:pointer;font-weight:600}}.outcome{{padding:16px;border-left:4px solid #ffd280;background:#1c2935}}
</style></head><body><main><p class="label">PROOFSMITH / RECORDED LIVE COMPARISON</p><h1>{headline}</h1>
<p class="outcome">{escape(metrics["claim"])}. Model: {escape(lock["model"])} through the official ByteAsk provider. {len(rows)} / 5 recorded case attempts. Additional purchases: $0.</p>
<div class="cards"><div class="card">Incorrect repairs accepted<strong>{metrics["byteask_incorrect_accepted"]} → {metrics["augmented_incorrect_accepted"]}</strong>ByteAsk → ByteAsk + gate</div>
<div class="card">Correct repairs accepted<strong>{metrics["byteask_correct_accepted"]} → {metrics["augmented_correct_accepted"]}</strong>ByteAsk → ByteAsk + gate</div>
<div class="card">Repair time<strong>{sum(r["wall_s"] for r in rows):.1f}s</strong>Total model/CLI wall time</div>
<div class="card">Gate overhead<strong>{sum(r["gate_wall_s"] for r in rows):.1f}s</strong>Total additional verification time</div></div>
<p>Each row compares two acceptance decisions for the <strong>same repair</strong>. ByteAsk receives the supplied regression, its native tools and normal compiler tools. Proofsmith adds a frozen check after the repair. The independent evaluator uses additional inputs to assess the candidate separately.</p>
<div class="table"><table><thead><tr><th>Case</th><th>ByteAsk decision</th><th>Independent evaluator</th><th>Frozen gate</th><th>With gate</th><th>Repair + gate</th></tr></thead><tbody>{''.join(table)}</tbody></table></div>
<p>Stop reason: {escape(collection.get("stop_reason") or "Completed all selected cases")}. Existing allowance usage after the last case: <code>{escape(json.dumps(last_usage, sort_keys=True))}</code>. Usage percentages are not dollar costs. No purchase, top-up, upgrade or fallback provider was used.</p>
<p>These are five authored synthetic C++ cases. They cannot establish broad superiority, novel vulnerability discovery or general patch correctness. This test evaluates final acceptance, not a better repair model or automatic verifier generation. An all-correct ByteAsk baseline gives no demonstrated advantage. Native tools may be absent from this CLI's JSONL; the final response can describe their outputs.</p>
<p>{link(scored / "results.json", "Recorded results")} · {link(live / "execution-lock.json", "Pinned execution settings")} · {link(live / "observations.json", "Collected observations")} · {link(experiment / "index.html", "Offline controls")} · {link(ROOT / "docs/byteask-live-comparison.md", "Run notes")}</p>
<p>Frozen protocol SHA-256: <code>{results["protocol_sha256"]}</code>. Receipts bind recorded bytes; they are not authorship signatures.</p>
{''.join(details)}</main></body></html>'''
    report.write_text(body, encoding="utf-8")
    print(json.dumps({"report": str(report), "metrics": metrics}))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--live", type=Path, default=ROOT / "experiments/byteask-comparison/live-v1")
    parser.add_argument("--scored", type=Path, default=ROOT / "experiments/byteask-comparison/live-v1-score")
    args = parser.parse_args()
    render(args.live.resolve(), args.scored.resolve())
