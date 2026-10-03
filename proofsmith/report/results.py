"""Render experiment results with a JSON pointer for every measured value."""
from __future__ import annotations

import json
from proofsmith import config
from proofsmith.report.site import _trajectory_href


def render_results(env, common: dict) -> dict | None:
    path = config.RESULTS / "summary.json"
    if not path.is_file():
        return None
    summary = json.loads(path.read_text())
    dest = config.SITE / "results"
    dest.mkdir(parents=True, exist_ok=True)
    instances = {}
    if summary.get("protocol_id"):
        root = config.RESULTS / "eval" / summary["protocol_id"]
        for track in summary["tracks"]:
            instances[track] = []
            protocol_path = config.REPO / "docs/protocol.json"
            protocol = json.loads(protocol_path.read_text()) if protocol_path.exists() else {"tracks": {}}
            for name in protocol.get("tracks", {}).get(track, []):
                rows = []
                for system in ("b0", "b1", "proofsmith"):
                    verdict = root / track / name / f"{system}.json"
                    if verdict.exists():
                        value = json.loads(verdict.read_text())
                        rows.append({"system": system, "value": value,
                            "source": verdict.relative_to(config.REPO).as_posix() + "#",
                            "trajectory": _trajectory_href(value.get("trajectory")) if value.get("trajectory") else None})
                    else:
                        rows.append({"system": system, "value": None})
                folder = dest / track / name
                folder.mkdir(parents=True, exist_ok=True)
                (folder / "index.html").write_text(env.get_template("result_instance.html.j2").render(
                    instance_id=name, rows=rows, **common), encoding="utf-8")
                instances[track].append(name)
    (dest / "index.html").write_text(env.get_template("results.html.j2").render(
        summary=summary, instances=instances, **common), encoding="utf-8")
    return summary
