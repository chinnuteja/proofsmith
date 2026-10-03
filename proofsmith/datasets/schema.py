"""Instance schemas and source-tree helpers."""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from proofsmith.config import REPO


class Source(BaseModel):
    kind: Literal["dir", "git"]
    path: str | None = None
    url: str | None = None
    commit: str | None = None


class Issue(BaseModel):
    title: str
    body: str
    url: str | None = None
    rewritten: bool = False
    mentions_fix: bool = False


class BuildRecipe(BaseModel):
    system: Literal["cmake", "make", "custom"]
    cmake_args: list[str] = []
    targets: list[str] = []
    jobs: int = 4
    custom_script: str | None = None
    test_command: str | None = None


class Instance(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    schema_version: str = Field(alias="schema")
    id: str
    track: Literal["demo", "micro", "A", "B"]
    source: Source
    issue: Issue
    build: BuildRecipe


class Fixed(BaseModel):
    kind: Literal["patch", "dir", "git"]
    path: str | None = None
    commit: str | None = None


class HiddenInstance(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    schema_version: str = Field(alias="schema")
    id: str
    fixed: Fixed
    bug_class: Literal["deadlock", "race", "lifetime", "ub", "behavioral", "none"]
    fix_files: list[str]
    dev_tests: list[str] = []
    notes: str = ""


def _resolve_repo_path(path: str) -> Path:
    candidate = Path(path)
    if not candidate.is_absolute():
        candidate = REPO / candidate
    return candidate


def materialize(instance: Instance, dest: Path) -> Path:
    dest = Path(dest)
    if dest.exists():
        shutil.rmtree(dest)
    dest.parent.mkdir(parents=True, exist_ok=True)
    source = instance.source
    if source.kind == "dir":
        if not source.path:
            raise ValueError("dir source requires path")
        shutil.copytree(_resolve_repo_path(source.path), dest)
        return dest
    if not source.url or not source.commit:
        raise ValueError("git source requires url and commit")
    from proofsmith.datasets.check import ensure_worktree
    from proofsmith.datasets.mine import mirror_path

    wt = dest.parent / f"{dest.name}.wt"
    ensure_worktree(source.url, source.commit, wt)
    if dest.exists():
        shutil.rmtree(dest)
    shutil.copytree(wt, dest, ignore=shutil.ignore_patterns(".git"))
    subprocess.run(
        ["git", "-C", str(mirror_path(source.url)), "worktree", "remove", "--force", str(wt)],
        check=False,
    )
    if wt.exists():
        shutil.rmtree(wt, ignore_errors=True)
    return dest


def apply_patch(repo: Path, patch: Path) -> None:
    repo = Path(repo)
    patch = Path(patch)
    attempts = [
        ["git", "apply", "--unsafe-paths", str(patch)],
        ["patch", "-p1", "--forward", "--input", str(patch)],
    ]
    errors: list[str] = []
    for cmd in attempts:
        proc = subprocess.run(
            cmd,
            cwd=repo,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            check=False,
            text=True,
        )
        if proc.returncode == 0:
            return
        errors.append(f"{' '.join(cmd)}\n{proc.stdout}")
    raise RuntimeError("patch failed\n" + "\n".join(errors))
