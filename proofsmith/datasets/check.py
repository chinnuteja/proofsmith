"""Validate Track B instances, including sanitizer builds."""

from __future__ import annotations

import json
import os
import signal
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path

from proofsmith.config import REPO, RESULTS, WORK
from proofsmith.datasets.mine import is_test_path, mirror_path, org_repo
from proofsmith.datasets.schema import BuildRecipe, HiddenInstance, Instance
from proofsmith.oracles.builds import build_variant

BUILD_TIMEOUT_S = 20 * 60
VARIANTS = ("asan_ubsan", "tsan")
CLASSES = ("deadlock", "race", "lifetime", "ub")


@dataclass
class InstanceCheck:
    id: str
    schema_ok: bool
    issue_ok: bool
    separation_ok: bool
    builds: dict
    fix_size: dict
    bug_class: str = ""
    repo: str = ""
    problems: list[str] = field(default_factory=list)


@dataclass
class CheckReport:
    instances: list[InstanceCheck]
    counts: dict[str, int]
    total: int
    mentions_fix: int
    concurrency: int

    def as_dict(self) -> dict:
        rows = []
        for item in self.instances:
            visible = _load_visible(item.id)
            hidden_path = _hidden_path(item.id)
            hidden = json.loads(hidden_path.read_text(encoding="utf-8")) if hidden_path.is_file() else {}
            url = ((visible.get("issue") or {}).get("url")) if visible else None
            title = ((visible.get("issue") or {}).get("title")) if visible else ""
            rows.append(
                {
                    "id": item.id,
                    "repo": item.repo,
                    "issue_url": url,
                    "issue_title": title,
                    "rewritten": bool((visible.get("issue") or {}).get("rewritten")) if visible else False,
                    "mentions_fix": bool((visible.get("issue") or {}).get("mentions_fix")) if visible else False,
                    "fix_files": item.fix_size.get("files", 0),
                    "fix_lines": item.fix_size.get("lines", 0),
                    "bug_class": item.bug_class,
                    "builds": item.builds,
                    "schema_ok": item.schema_ok,
                    "issue_ok": item.issue_ok,
                    "separation_ok": item.separation_ok,
                }
            )
        return {
            "schema": "proofsmith.trackb_check/1",
            "total": self.total,
            "counts": self.counts,
            "concurrency": self.concurrency,
            "mentions_fix": self.mentions_fix,
            "instances": rows,
        }


def track_dir(track: str) -> Path:
    name = {"A": "trackA", "B": "trackB"}.get(track, f"track{track}")
    return REPO / "data" / name


def _instances_dir(track: str) -> Path:
    return track_dir(track) / "instances"


def _hidden_dir(track: str) -> Path:
    return track_dir(track) / "hidden"


def _hidden_path(instance_id: str, track: str = "B") -> Path:
    return _hidden_dir(track) / f"{instance_id}.json"


def _diff_path(instance_id: str, track: str = "B") -> Path:
    return _hidden_dir(track) / f"{instance_id}.fix.diff"


def _raw_path(instance_id: str, track: str = "B") -> Path:
    return track_dir(track) / "raw" / f"{instance_id}.issue.json"


def _load_visible(instance_id: str, track: str = "B") -> dict:
    path = _instances_dir(track) / f"{instance_id}.json"
    return json.loads(path.read_text(encoding="utf-8"))


def list_instance_ids(track: str) -> list[str]:
    root = _instances_dir(track)
    if not root.is_dir():
        return []
    return sorted(path.stem for path in root.glob("*.json"))


def separation_problems(visible_text: str, issue_text: str, fixed_sha: str, diff: str, fix_files: list[str], mentions_fix: bool) -> list[str]:
    problems: list[str] = []
    if "bug_class" in visible_text:
        problems.append("visible JSON mentions bug_class")
    if fixed_sha and fixed_sha in visible_text:
        problems.append("visible JSON contains the fixed sha")
    prefix = fixed_sha[:7] if fixed_sha else ""
    if len(prefix) >= 7 and prefix in visible_text:
        problems.append("visible JSON contains the fixed sha prefix")
    for line in diff.splitlines():
        if len(line) >= 20 and line in visible_text:
            problems.append("visible JSON contains a fix diff line")
            break
    if not mentions_fix:
        for path in fix_files:
            base = Path(path).name
            if base and base in issue_text:
                problems.append(f"issue text contains fix file {base}")
                break
    return problems


def fix_size(diff: str) -> dict[str, int]:
    files: set[str] = set()
    lines = 0
    current: str | None = None
    for line in diff.splitlines():
        if line.startswith("diff --git "):
            parts = line.split()
            current = parts[-1][2:] if parts and parts[-1].startswith("b/") else None
            continue
        if line.startswith("+++ ") or line.startswith("--- ") or line.startswith("@@") or line.startswith("index ") or line.startswith("new file") or line.startswith("deleted file"):
            continue
        if current and (line.startswith("+") or line.startswith("-")):
            if is_test_path(current):
                continue
            suffix = Path(current).suffix.lower()
            if suffix not in {".c", ".cc", ".cpp", ".cxx", ".h", ".hh", ".hpp", ".hxx", ".ipp", ".inl"}:
                continue
            files.add(current)
            lines += 1
    return {"files": len(files), "lines": lines}


def _full_sha(repo: Path, sha: str) -> str:
    proc = subprocess.run(
        ["git", "-C", str(repo), "rev-parse", sha],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        check=False,
        text=True,
    )
    if proc.returncode != 0:
        raise RuntimeError(proc.stdout)
    return proc.stdout.strip()


def ensure_worktree(url: str, commit: str, dest: Path) -> Path:
    mirror = mirror_path(url)
    if not (mirror / ".git").exists():
        from proofsmith.datasets.mine import clone_mirror

        clone_mirror(url)
    dest = Path(dest)
    dest.parent.mkdir(parents=True, exist_ok=True)
    full = _full_sha(mirror, commit)
    if dest.exists():
        proc = subprocess.run(
            ["git", "-C", str(dest), "rev-parse", "HEAD"],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            check=False,
            text=True,
        )
        if proc.returncode == 0 and proc.stdout.strip() == full:
            return dest
        subprocess.run(["git", "-C", str(mirror), "worktree", "remove", "--force", str(dest)], check=False)
        if dest.exists():
            subprocess.run(["rm", "-rf", str(dest)], check=False)
    proc = subprocess.run(
        ["git", "-C", str(mirror), "worktree", "add", "--detach", str(dest), full],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        check=False,
        text=True,
    )
    if proc.returncode != 0:
        raise RuntimeError(proc.stdout)
    return dest


def _cache_ready(repo: Path, variant: str, recipe: BuildRecipe) -> bool:
    from proofsmith.oracles.builds import build_key

    cache = WORK / "cache" / "builds" / build_key(repo, variant, recipe)
    return (cache / ".proofsmith-ok").is_file() and (cache / "compile_commands.json").is_file()


def _log_oom(log_path: Path | None) -> bool:
    if log_path is None or not log_path.is_file():
        return False
    text = log_path.read_text(encoding="utf-8", errors="replace").lower()
    needles = ("killed", "out of memory", "cannot allocate", "std::bad_alloc", "oom")
    return any(needle in text for needle in needles)


def build_tree(repo: Path, variant: str, recipe: BuildRecipe, out_root: Path) -> tuple[bool, str]:
    if _cache_ready(repo, variant, recipe):
        result = build_variant(repo, variant, recipe, out_root)
        return result.ok, ""
    recipe_path = out_root / f".recipe-{variant}.json"
    out_root.mkdir(parents=True, exist_ok=True)
    recipe_path.write_text(recipe.model_dump_json(), encoding="utf-8", newline="\n")
    code = (
        "import sys\n"
        "from pathlib import Path\n"
        "from proofsmith.datasets.schema import BuildRecipe\n"
        "from proofsmith.oracles.builds import build_variant\n"
        "repo, variant, out_root, recipe_path = sys.argv[1:]\n"
        "recipe = BuildRecipe.model_validate_json(Path(recipe_path).read_text(encoding='utf-8'))\n"
        "result = build_variant(Path(repo), variant, recipe, Path(out_root))\n"
        "print('BUILD_OK' if result.ok else 'BUILD_FAIL')\n"
        "print(result.log_path)\n"
    )
    proc = subprocess.Popen(
        [sys.executable, "-c", code, str(repo), variant, str(out_root), str(recipe_path)],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        start_new_session=True,
    )
    try:
        stdout, _ = proc.communicate(timeout=BUILD_TIMEOUT_S)
    except subprocess.TimeoutExpired:
        os.killpg(proc.pid, signal.SIGKILL)
        proc.wait(timeout=30)
        return False, "timeout"
    lines = [line.strip() for line in (stdout or "").splitlines() if line.strip()]
    status = lines[-2] if len(lines) >= 2 else ""
    log_path = Path(lines[-1]) if lines else None
    if status != "BUILD_OK":
        if _log_oom(log_path):
            return False, "oom"
        return False, "build failed"
    return True, ""


def _issue_ok(instance: Instance, instance_id: str, track: str) -> bool:
    issue = instance.issue
    if not issue.title.strip() or not issue.body.strip() or not issue.url:
        return False
    raw = _raw_path(instance_id, track)
    if not raw.is_file():
        return False
    try:
        payload = json.loads(raw.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return False
    return isinstance(payload, dict) and bool(payload.get("html_url") or payload.get("url") or payload.get("body") is not None)


def check_dataset(track: str) -> CheckReport:
    ids = list_instance_ids(track)
    checks: list[InstanceCheck] = []
    counts = {name: 0 for name in CLASSES}
    mentions = 0
    for instance_id in ids:
        problems: list[str] = []
        visible_path = _instances_dir(track) / f"{instance_id}.json"
        visible_text = visible_path.read_text(encoding="utf-8")
        schema_ok = True
        try:
            instance = Instance.model_validate_json(visible_text)
        except Exception as exc:
            schema_ok = False
            problems.append(f"instance schema: {exc}")
            instance = None
        hidden_path = _hidden_path(instance_id, track)
        bug_class = ""
        fixed_sha = ""
        fix_files: list[str] = []
        try:
            hidden = HiddenInstance.model_validate_json(hidden_path.read_text(encoding="utf-8"))
        except Exception as exc:
            schema_ok = False
            problems.append(f"hidden schema: {exc}")
            hidden = None
        if instance is not None and instance.id != instance_id:
            schema_ok = False
            problems.append("instance id mismatch")
        if hidden is not None:
            bug_class = hidden.bug_class
            fix_files = list(hidden.fix_files)
            if hidden.id != instance_id:
                schema_ok = False
                problems.append("hidden id mismatch")
            if hidden.fixed.kind == "git":
                fixed_sha = hidden.fixed.commit or ""
        diff_file = _diff_path(instance_id, track)
        diff = diff_file.read_text(encoding="utf-8") if diff_file.is_file() else ""
        size = fix_size(diff) if diff else {"files": len(fix_files), "lines": 0}
        issue_text = ""
        repo_name = ""
        issue_ok = False
        if instance is not None:
            issue_text = f"{instance.issue.title}\n{instance.issue.body}"
            issue_ok = _issue_ok(instance, instance_id, track)
            if instance.source.url:
                org, name = org_repo(instance.source.url)
                repo_name = f"{org}/{name}"
            if instance.issue.mentions_fix:
                mentions += 1
        leaked = separation_problems(
            visible_text,
            issue_text,
            fixed_sha,
            diff,
            fix_files,
            bool(instance and instance.issue.mentions_fix),
        )
        problems.extend(leaked)
        builds = {side: {variant: False for variant in VARIANTS} for side in ("buggy", "fixed")}
        build_notes: list[str] = []
        if instance is not None and instance.source.kind == "git" and instance.source.url and instance.source.commit and fixed_sha:
            trees = {
                "buggy": (instance.source.commit, WORK / "trackb" / instance_id / "buggy"),
                "fixed": (fixed_sha, WORK / "trackb" / instance_id / "fixed"),
            }
            out_root = WORK / "trackb" / instance_id / "out"
            for side, (commit, dest) in trees.items():
                try:
                    tree = ensure_worktree(instance.source.url, commit, dest)
                except Exception as exc:
                    problems.append(f"{side} checkout: {exc}")
                    continue
                for variant in VARIANTS:
                    ok, note = build_tree(tree, variant, instance.build, out_root)
                    builds[side][variant] = ok
                    if not ok:
                        build_notes.append(f"{side} {variant}: {note or 'build failed'}")
        problems.extend(build_notes)
        if bug_class in counts:
            counts[bug_class] += 1
        checks.append(
            InstanceCheck(
                id=instance_id,
                schema_ok=schema_ok,
                issue_ok=issue_ok,
                separation_ok=not leaked,
                builds=builds,
                fix_size=size,
                bug_class=bug_class,
                repo=repo_name,
                problems=problems,
            )
        )
    total = len(checks)
    report = CheckReport(
        instances=checks,
        counts=counts,
        total=total,
        mentions_fix=mentions,
        concurrency=counts["deadlock"] + counts["race"],
    )
    if track == "B":
        RESULTS.mkdir(parents=True, exist_ok=True)
        path = RESULTS / "trackB_check.json"
        path.write_text(json.dumps(report.as_dict(), indent=2) + "\n", encoding="utf-8", newline="\n")
    return report


def main(argv: list[str] | None = None) -> int:
    import argparse

    parser = argparse.ArgumentParser(prog="trackb-check")
    parser.add_argument("--track", default="B")
    args = parser.parse_args(argv)
    report = check_dataset(args.track)
    print(json.dumps({"total": report.total, "counts": report.counts, "concurrency": report.concurrency}))
    failed = [item for item in report.instances if item.problems or not all(item.builds[side][variant] for side in item.builds for variant in item.builds[side])]
    for item in failed:
        print(f"FAIL {item.id}: {'; '.join(item.problems)}")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
