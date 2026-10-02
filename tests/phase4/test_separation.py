"""Visible Track B JSON must not leak the fix."""

from __future__ import annotations

import json
from pathlib import Path

from proofsmith.config import REPO
from proofsmith.datasets.check import separation_problems

ROOT = REPO / "data" / "trackB"


def test_visible_json_does_not_leak_the_fix():
    paths = sorted((ROOT / "instances").glob("*.json"))
    assert paths
    for path in paths:
        visible = path.read_text(encoding="utf-8")
        payload = json.loads(visible)
        hidden = json.loads((ROOT / "hidden" / f"{path.stem}.json").read_text(encoding="utf-8"))
        diff = (ROOT / "hidden" / f"{path.stem}.fix.diff").read_text(encoding="utf-8")
        issue = payload["issue"]
        problems = separation_problems(
            visible,
            f"{issue['title']}\n{issue['body']}",
            hidden["fixed"].get("commit") or "",
            diff,
            hidden.get("fix_files") or [],
            bool(issue.get("mentions_fix")),
        )
        assert problems == [], f"{path.stem}: {problems}"
        assert "bug_class" not in visible
