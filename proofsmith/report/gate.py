"""Self-contained HTML receipts: local assets, escaped evidence, no scripts or trackers."""
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape


def render_receipt(out: Path, receipt: dict) -> None:
    environment = Environment(loader=FileSystemLoader(Path(__file__).parent / "templates"),
                              autoescape=select_autoescape(default=True))
    examples = {}
    for side in ("baseline", "candidate"):
        for run in receipt.get(side, {}).get("runs", []):
            if run["matches_target"] or run["exit_code"] != 0:
                examples[side] = (out / run["log"]).read_text(errors="replace")
                break
    html = environment.get_template("gate_receipt.html.j2").render(receipt=receipt, examples=examples)
    (out / "index.html").write_text(html, encoding="utf-8")


def render_demo(out: Path, summary: dict) -> None:
    environment = Environment(loader=FileSystemLoader(Path(__file__).parent / "templates"),
                              autoescape=select_autoescape(default=True))
    (out / "index.html").write_text(environment.get_template("gate_demo.html.j2").render(summary=summary),
                                   encoding="utf-8")
