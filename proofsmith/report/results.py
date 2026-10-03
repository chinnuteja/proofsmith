"""Render experiment results with a JSON pointer for every measured value."""
from __future__ import annotations

import json
from proofsmith import config
from proofsmith.report.site import _trajectory_href


def render_results(env, common: dict, *, summary_path=None, protocol_path=None, output_root=None, prefix='/results') -> dict | None:
    path = summary_path or config.RESULTS / "summary.json"
    if not path.is_file():
        return None
    summary = json.loads(path.read_text())
    dest = output_root or config.SITE / "results"
    dest.mkdir(parents=True, exist_ok=True)
    summary_source = path.relative_to(config.REPO).as_posix()
    history_links = []
    if summary_path is None:
        for prior in sorted((config.RESULTS / 'protocol-history').glob('*/summary.json')):
            old = json.loads(prior.read_text())
            old_protocol = config.REPO / 'docs/protocol-history' / (old['protocol_sha256'] + '.json')
            if old_protocol.is_file():
                route = '/results/history/' + old['protocol_id']
                render_results(env, common, summary_path=prior, protocol_path=old_protocol,
                    output_root=dest / 'history' / old['protocol_id'], prefix=route)
                history_links.append({'id': old['protocol_id'], 'href': route + '/'})
    instances = {}
    if summary.get("protocol_id"):
        root = config.RESULTS / "eval" / summary["protocol_id"]
        for track in summary["tracks"]:
            instances[track] = []
            protocol_file = protocol_path or config.REPO / "docs/protocol.json"
            protocol = json.loads(protocol_file.read_text()) if protocol_file.exists() else {"tracks": {}}
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
        summary=summary, instances=instances, summary_source=summary_source,
        results_prefix=prefix, history_links=history_links, **common), encoding="utf-8")
    return summary
