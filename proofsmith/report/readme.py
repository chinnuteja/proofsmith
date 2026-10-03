"""Generate a report and a draft message; never infer unmeasured successes."""
from __future__ import annotations

import json
from pathlib import Path

from jinja2 import Environment, FileSystemLoader
from proofsmith import config
from proofsmith.eval.runner import atomic_json
from proofsmith.report.site import format_number


def pointer(value, path: str):
    for token in path.lstrip("/").split("/") if path else []:
        token = token.replace("~1", "/").replace("~0", "~")
        value = value[int(token)] if isinstance(value, list) else value[token]
    return value


def generate_readme() -> None:
    sources = []

    def number(source: str) -> str:
        name, path = source.split("#", 1)
        value = pointer(json.loads((config.REPO / name).read_text()), path)
        rendered = format_number(value) if value is not None else "pending"
        sources.append({"source": source, "rendered": rendered})
        return rendered

    summary_path = config.RESULTS / "summary.json"
    summary = json.loads(summary_path.read_text()) if summary_path.exists() else None
    demo_path = config.RESULTS / "demo/orderd.json"
    demo = json.loads(demo_path.read_text()) if demo_path.exists() else None
    env = Environment(loader=FileSystemLoader(Path(__file__).parent / "templates"), autoescape=False)
    context = {"summary": summary, "demo": demo, "number": number}
    text = env.get_template("README.md.j2").render(**context)
    (config.REPO / "README.md").write_text(text.strip() + "\n", encoding="utf-8")
    atomic_json(config.REPO / "README.sources.json", {"schema": "proofsmith.sources/1", "values": sources})
    message_sources_start = len(sources)
    message = env.get_template("send_message.md.j2").render(**context)
    (config.REPO / "docs/send_message.md").write_text(message.strip() + "\n", encoding="utf-8")
    atomic_json(config.REPO / "docs/send_message.sources.json",
                {"schema": "proofsmith.sources/1", "values": sources[message_sources_start:]})
    generate_cases()


def generate_cases() -> None:
    dest = config.REPO / "docs/worked_cases"
    dest.mkdir(parents=True, exist_ok=True)
    root = config.RESULTS / "summary.json"
    summary = json.loads(root.read_text()) if root.exists() else {}
    protocol = summary.get("protocol_id")
    selected = {"sanitizer_win": None, "plain_test_win": None, "honest_failure": None}
    if protocol:
        for track_dir in sorted((config.RESULTS / "eval" / protocol).glob("*")):
            for directory in sorted(track_dir.glob("*")):
                p = directory / "proofsmith.json"
                b = directory / "b1.json"
                if not p.exists():
                    continue
                row = json.loads(p.read_text())
                baseline = json.loads(b.read_text()) if b.exists() else None
                win = row["f2p"] and row["alignment"]["strict"] and baseline and not (baseline["f2p"] and baseline["alignment"]["strict"])
                category = "sanitizer_win" if win and row["oracle"] in {"tsan", "asan_ubsan"} else "plain_test_win" if win and row["oracle"] == "assertion" else "honest_failure" if not row["f2p"] else None
                if category and selected[category] is None:
                    selected[category] = (p, row, b, baseline)
    for category, case in selected.items():
        title = category.replace("_", " ").capitalize()
        if case is None:
            text = f"# {title}\n\nNo qualifying measured case has been selected from the frozen protocol. This page is pending evaluation; it makes no success claim.\n"
        else:
            p, row, b, baseline = case
            from proofsmith.eval.runner import load_case
            instance, _ = load_case(row["track"], row["instance_id"])
            text = f"# {title}: {instance.id}\n\n{instance.issue.title}\n\n{instance.issue.body}\n\n"
            for path, item in ((p, row), (b, baseline)):
                if item:
                    rel = path.relative_to(config.REPO).as_posix()
                    text += f"{item['system']}: raw F→P `{item['f2p']}`, strict alignment `{item['alignment']['strict']}`. [Full verdict](../../{rel}).\n\n"
                    if item.get("trajectory"):
                        text += f"[Generation trajectory](../../{item['trajectory']}).\n\n"
                    if item.get("error"):
                        text += f"Recorded error: `{item['error']}`.\n\n"
        (dest / f"{category}.md").write_text(text, encoding="utf-8")
