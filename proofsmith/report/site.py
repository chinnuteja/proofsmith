"""Render the static Proofsmith site."""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

from jinja2 import Environment, FileSystemLoader

from proofsmith.config import REPO, RESULTS, RUNS, SITE

TEMPLATE_DIR = Path(__file__).resolve().parent / "templates"
STATIC_DIR = Path(__file__).resolve().parent / "static"


def format_number(value: object) -> str:
    """Format a JSON value the way the site prints it.

    Browser checks compare element text to this function, so every rendered
    data-source value must go through it.
    """
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, int):
        return str(value)
    if isinstance(value, float):
        return format(value, ".12g")
    if value is None:
        return ""
    return str(value)


def git_short_sha() -> str:
    try:
        proc = subprocess.run(
            ["git", "-C", str(REPO), "rev-parse", "--short", "HEAD"],
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            check=True,
            text=True,
        )
    except (subprocess.CalledProcessError, FileNotFoundError):
        return "unknown"
    sha = proc.stdout.strip()
    return sha or "unknown"


def _load_toolchain() -> dict:
    path = RESULTS / "toolchain.json"
    if not path.is_file():
        return {"clang_version": "UNKNOWN", "probes": []}
    return json.loads(path.read_text(encoding="utf-8"))


_ROW_LABELS = (
    ("buggy", "buggy"),
    ("timing_backoff", "timing backoff"),
    ("scoped_cancel", "ByteAsk's fix (scoped_lock in cancel)"),
    ("consistent_order", "consistent lock order"),
)

_CELL_LABELS = {
    "ctest": "existing tests (ctest)",
    "stress": "stress repro ×20",
    "verifier": "Proofsmith check ×20",
}


def _pointer_token(key: str) -> str:
    return key.replace("~", "~0").replace("/", "~1")


def _load_demo() -> dict | None:
    path = RESULTS / "demo" / "orderd.json"
    if not path.is_file():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def _demo_rows(payload: dict) -> list[dict]:
    rows = []
    for key, label in _ROW_LABELS:
        row = payload["rows"][key]
        cells = []
        for name, left_key, right_key in (
            ("ctest", "passed", "total"),
            ("stress", "fails", "n"),
            ("verifier", "fails", "n"),
        ):
            block = row[name]
            left = block[left_key]
            right = block[right_key]
            if name == "ctest":
                pill = "pill-pass" if left == right else "pill-fail"
            else:
                pill = "pill-pass" if left == 0 else "pill-fail"
            base = f"results/demo/orderd.json#/rows/{key}/{name}"
            cells.append(
                {
                    "name": name,
                    "label": _CELL_LABELS[name],
                    "pill": pill,
                    "left": left,
                    "right": right,
                    "left_source": f"{base}/{left_key}",
                    "right_source": f"{base}/{right_key}",
                }
            )
        rows.append({"id": key, "label": label, "cells": cells})
    return rows


def _render_demo(env: Environment, git_sha: str) -> None:
    payload = _load_demo()
    if payload is None:
        return
    files = payload.get("verifier", {}).get("files", {})
    harness_sha = files.get("harness/harness.cpp", "")
    html = env.get_template("demo.html.j2").render(
        show_demo=True,
        show_runs=bool(_load_run_summaries()),
        git_sha=git_sha,
        issue=payload["issue"],
        oracle=payload.get("oracle", ""),
        verifier=payload["verifier"],
        strip=payload.get("strip") or [],
        harness_sha=harness_sha,
        harness_pointer=_pointer_token("harness/harness.cpp"),
        rows=_demo_rows(payload),
        raw_report=payload.get("raw_report_buggy", ""),
    )
    demo_dir = SITE / "demo"
    demo_dir.mkdir(parents=True, exist_ok=True)
    (demo_dir / "index.html").write_text(html, encoding="utf-8", newline="\n")


def _status_pill(status: str) -> str:
    if status == "finished":
        return "pass"
    if status == "abstained":
        return "warn"
    if status in {"error", "budget_exhausted"}:
        return "fail"
    return "info"


def _load_run_summaries() -> list[dict]:
    if not RUNS.is_dir():
        return []
    found: list[dict] = []
    for path in sorted(RUNS.glob("*/summary.json")):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            continue
        if not isinstance(data, dict):
            continue
        data.setdefault("run_id", path.parent.name)
        data["pill"] = _status_pill(str(data.get("status") or ""))
        found.append(data)
    return found


def _load_events(run_id: str) -> list[dict]:
    path = RUNS / run_id / "trajectory.jsonl"
    if not path.is_file():
        return []
    events: list[dict] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            events.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return events


def _run_steps(events: list[dict]) -> list[dict]:
    grouped: dict[int, dict] = {}
    for event in events:
        kind = event.get("type")
        if kind not in {"llm_response", "tool_call", "tool_result"}:
            continue
        step = int(event.get("step") or 0)
        bucket = grouped.setdefault(
            step,
            {"step": step, "content": "", "calls": [], "results": []},
        )
        if kind == "llm_response":
            bucket["content"] = event.get("content") or ""
        elif kind == "tool_call":
            bucket["calls"].append(
                {
                    "name": event.get("name") or "",
                    "arguments": json.dumps(event.get("arguments") or {}, indent=2, ensure_ascii=False),
                }
            )
        else:
            bucket["results"].append(
                {
                    "name": event.get("name") or "tool",
                    "output": event.get("output") or "",
                }
            )
    return [grouped[key] for key in sorted(grouped)]


def _copy_run_data(runs: list[dict]) -> None:
    dest_root = SITE / "data" / "runs"
    dest_root.mkdir(parents=True, exist_ok=True)
    for run in runs:
        run_id = str(run.get("run_id") or "")
        source = RUNS / run_id / "summary.json"
        if source.is_file():
            shutil.copyfile(source, dest_root / f"{run_id}.json")


def _render_runs(env: Environment, git_sha: str, runs: list[dict]) -> None:
    if not runs:
        return
    runs_dir = SITE / "runs"
    runs_dir.mkdir(parents=True, exist_ok=True)
    index = env.get_template("runs.html.j2").render(
        git_sha=git_sha,
        show_demo=_load_demo() is not None,
        show_runs=True,
        runs=runs,
    )
    (runs_dir / "index.html").write_text(index, encoding="utf-8", newline="\n")
    for run in runs:
        run_id = str(run["run_id"])
        steps = _run_steps(_load_events(run_id))
        tokens = float(run.get("tokens") or 0)
        maximum = float(run.get("max_total_tokens") or 0)
        pct = 0.0 if maximum <= 0 else min(100.0, tokens / maximum * 100.0)
        html = env.get_template("run.html.j2").render(
            git_sha=git_sha,
            show_demo=_load_demo() is not None,
            show_runs=True,
            summary=run,
            steps=steps,
            pill=run.get("pill") or "info",
            token_pct=f"{pct:.4f}",
        )
        page = runs_dir / run_id
        page.mkdir(parents=True, exist_ok=True)
        (page / "index.html").write_text(html, encoding="utf-8", newline="\n")


def build_site() -> None:
    SITE.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(STATIC_DIR / "site.css", SITE / "site.css")
    payload = _load_toolchain()
    probes = []
    for item in payload.get("probes", []):
        rel = item.get("output_path") or ""
        body = ""
        if rel:
            fixture = REPO / rel
            if fixture.is_file():
                body = fixture.read_text(encoding="utf-8", errors="replace")
        ok = bool(item.get("ok"))
        probes.append(
            {
                **item,
                "output": body,
                "pill": "pill-pass" if ok else "pill-fail",
                "pill_text": "pass" if ok else "fail",
            }
        )
    env = Environment(loader=FileSystemLoader(TEMPLATE_DIR), autoescape=True)
    env.filters["fmt"] = format_number
    sha = git_short_sha()
    runs = _load_run_summaries()
    show_demo = _load_demo() is not None
    show_runs = bool(runs)
    html = env.get_template("index.html.j2").render(
        clang_version=payload.get("clang_version", "UNKNOWN"),
        probes=probes,
        git_sha=sha,
        show_demo=show_demo,
        show_runs=show_runs,
    )
    (SITE / "index.html").write_text(html, encoding="utf-8", newline="\n")
    _render_demo(env, sha)
    _copy_run_data(runs)
    _render_runs(env, sha, runs)
