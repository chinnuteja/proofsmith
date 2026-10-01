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
    html = env.get_template("index.html.j2").render(
        clang_version=payload.get("clang_version", "UNKNOWN"),
        probes=probes,
        git_sha=git_short_sha(),
    )
    (SITE / "index.html").write_text(html, encoding="utf-8", newline="\n")
