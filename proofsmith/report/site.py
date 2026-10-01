"""Render the static Proofsmith site."""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

from jinja2 import Environment, FileSystemLoader

from proofsmith.config import REPO, RESULTS, SITE

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
    sha = git_short_sha()
    show_demo = _load_demo() is not None
    html = env.get_template("index.html.j2").render(
        clang_version=payload.get("clang_version", "UNKNOWN"),
        probes=probes,
        git_sha=sha,
        show_demo=show_demo,
    )
    (SITE / "index.html").write_text(html, encoding="utf-8", newline="\n")
    _render_demo(env, sha)
