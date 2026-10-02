"""Track A: Multi-SWE-bench C++ instances, built locally with clang."""

from __future__ import annotations

import hashlib
import json
import shutil
from dataclasses import dataclass, field
from pathlib import Path

from proofsmith.config import REPO, RESULTS, WORK
from proofsmith.datasets.check import (
    build_tree,
    ensure_worktree,
    fix_size,
    separation_problems,
)
from proofsmith.datasets.mine import org_repo
from proofsmith.datasets.schema import BuildRecipe, HiddenInstance, Instance, apply_patch

VARIANTS = ("plain", "asan_ubsan")


@dataclass
class InstanceCheck:
    id: str
    schema_ok: bool
    separation_ok: bool
    builds: dict
    repo: str
    bug_class: str = ""
    problems: list[str] = field(default_factory=list)


@dataclass
class CheckReport:
    instances: list[InstanceCheck]
    total: int
    source_url: str
    source_revision: str

    def as_dict(self) -> dict:
        rows = []
        for item in self.instances:
            visible = json.loads((_instances() / f"{item.id}.json").read_text(encoding="utf-8"))
            hidden = json.loads((_hidden() / f"{item.id}.json").read_text(encoding="utf-8"))
            diff = (_hidden() / f"{item.id}.fix.diff").read_text(encoding="utf-8")
            size = fix_size(diff)
            rows.append(
                {
                    "id": item.id,
                    "repo": item.repo,
                    "issue_url": (visible.get("issue") or {}).get("url"),
                    "issue_title": (visible.get("issue") or {}).get("title") or "",
                    "base_commit": (visible.get("source") or {}).get("commit") or "",
                    "bug_class": item.bug_class,
                    "fix_files": size["files"],
                    "fix_lines": size["lines"],
                    "dev_tests": len(hidden.get("dev_tests") or []),
                    "builds": item.builds,
                    "schema_ok": item.schema_ok,
                    "separation_ok": item.separation_ok,
                }
            )
        repos: dict[str, int] = {}
        for row in rows:
            repos[row["repo"]] = repos.get(row["repo"], 0) + 1
        return {
            "schema": "proofsmith.tracka_check/1",
            "total": self.total,
            "repos": repos,
            "source_url": self.source_url,
            "source_revision": self.source_revision,
            "instances": rows,
        }


def track_root() -> Path:
    return REPO / "data" / "trackA"


def _instances() -> Path:
    return track_root() / "instances"


def _hidden() -> Path:
    return track_root() / "hidden"


def list_ids() -> list[str]:
    root = _instances()
    if not root.is_dir():
        return []
    return sorted(path.stem for path in root.glob("*.json"))


def load_source() -> tuple[str, str]:
    path = track_root() / "source.json"
    if not path.is_file():
        return "", ""
    payload = json.loads(path.read_text(encoding="utf-8"))
    return str(payload.get("url") or ""), str(payload.get("revision") or "")


def _fixed_tree(url: str, commit: str, diff_path: Path, dest: Path) -> Path:
    dest = Path(dest)
    digest = hashlib.sha256(diff_path.read_bytes()).hexdigest()
    marker_text = f"{commit} {digest}"
    if dest.exists():
        marker = dest / ".proofsmith-fixed"
        if marker.is_file() and marker.read_text(encoding="utf-8").strip() == marker_text:
            return dest
        shutil.rmtree(dest)
    buggy = ensure_worktree(url, commit, dest.parent / "_buggy_for_fixed")
    shutil.copytree(buggy, dest, ignore=shutil.ignore_patterns(".git"))
    apply_patch(dest, diff_path)
    (dest / ".proofsmith-fixed").write_text(f"{commit} {digest}\n", encoding="utf-8", newline="\n")
    return dest


def check_tracka() -> CheckReport:
    source_url, revision = load_source()
    checks: list[InstanceCheck] = []
    for instance_id in list_ids():
        problems: list[str] = []
        visible_path = _instances() / f"{instance_id}.json"
        visible_text = visible_path.read_text(encoding="utf-8")
        schema_ok = True
        try:
            instance = Instance.model_validate_json(visible_text)
        except Exception as exc:
            schema_ok = False
            problems.append(f"instance schema: {exc}")
            instance = None
        hidden_path = _hidden() / f"{instance_id}.json"
        diff_path = _hidden() / f"{instance_id}.fix.diff"
        bug_class = ""
        try:
            hidden = HiddenInstance.model_validate_json(hidden_path.read_text(encoding="utf-8"))
        except Exception as exc:
            schema_ok = False
            problems.append(f"hidden schema: {exc}")
            hidden = None
        if instance is not None and instance.id != instance_id:
            schema_ok = False
            problems.append("instance id mismatch")
        if hidden is not None and hidden.id != instance_id:
            schema_ok = False
            problems.append("hidden id mismatch")
        if hidden is not None:
            bug_class = hidden.bug_class
        diff = diff_path.read_text(encoding="utf-8") if diff_path.is_file() else ""
        issue_text = ""
        repo_name = ""
        if instance is not None:
            issue_text = f"{instance.issue.title}\n{instance.issue.body}"
            if instance.source.url:
                org, name = org_repo(instance.source.url)
                repo_name = f"{org}/{name}"
        fixed_sha = ""
        if hidden is not None and hidden.fixed.kind == "git":
            fixed_sha = hidden.fixed.commit or ""
        leaked = separation_problems(
            visible_text,
            issue_text,
            fixed_sha,
            diff,
            list(hidden.fix_files) if hidden is not None else [],
            bool(instance and instance.issue.mentions_fix),
        )
        problems.extend(leaked)
        builds = {side: {variant: False for variant in VARIANTS} for side in ("buggy", "fixed")}
        if (
            instance is not None
            and hidden is not None
            and instance.source.kind == "git"
            and instance.source.url
            and instance.source.commit
            and hidden.fixed.kind == "patch"
            and diff_path.is_file()
        ):
            root = WORK / "tracka" / instance_id
            try:
                buggy = ensure_worktree(instance.source.url, instance.source.commit, root / "buggy")
                fixed = _fixed_tree(instance.source.url, instance.source.commit, diff_path, root / "fixed")
            except Exception as exc:
                problems.append(f"checkout: {exc}")
            else:
                recipe: BuildRecipe = instance.build
                for side, tree in (("buggy", buggy), ("fixed", fixed)):
                    for variant in VARIANTS:
                        ok, note = build_tree(tree, variant, recipe, root / "out")
                        builds[side][variant] = ok
                        if not ok:
                            problems.append(f"{side} {variant}: {note or 'build failed'}")
        elif instance is not None:
            problems.append("missing git source or fix patch")
        checks.append(
            InstanceCheck(
                id=instance_id,
                schema_ok=schema_ok,
                separation_ok=not leaked,
                builds=builds,
                repo=repo_name,
                bug_class=bug_class,
                problems=problems,
            )
        )
    report = CheckReport(checks, len(checks), source_url, revision)
    RESULTS.mkdir(parents=True, exist_ok=True)
    (RESULTS / "trackA_check.json").write_text(
        json.dumps(report.as_dict(), indent=2) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    return report
