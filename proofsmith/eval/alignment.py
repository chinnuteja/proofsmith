"""Map a fix diff onto functions and score whether a failure landed there.

Alignment never changes fail-to-pass. A coverage timeout is unknown, and
both strict and relaxed stay false.
"""

from __future__ import annotations

import json
import re
import subprocess
from dataclasses import dataclass
from pathlib import Path

from proofsmith.oracles.signature import Frame

_HUNK = re.compile(r"^@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))? @@")


@dataclass(frozen=True)
class FuncRange:
    name: str
    file: str
    start: int
    end: int


@dataclass
class Alignment:
    strict: bool
    relaxed: bool
    unknown: bool
    hits: list[dict]

    def as_dict(self) -> dict:
        return {
            "strict": self.strict,
            "relaxed": self.relaxed,
            "unknown": self.unknown,
            "hits": list(self.hits),
        }


def _norm(path: str, repo_root: str) -> str:
    raw = Path(path)
    if raw.is_absolute():
        try:
            return raw.resolve().relative_to(Path(repo_root).resolve()).as_posix()
        except ValueError:
            return raw.as_posix()
    text = raw.as_posix()
    if text.startswith("./"):
        text = text[2:]
    return text


def _is_test_path(path: str) -> bool:
    return "test" in path.lower()


def _hunk_range(old_start: int, old_len: int) -> tuple[int, int]:
    if old_len == 0:
        return old_start, old_start + 1
    return old_start, old_start + old_len


def _diff_ranges(fix_diff: str) -> dict[str, list[tuple[int, int]]]:
    ranges: dict[str, list[tuple[int, int]]] = {}
    current: str | None = None
    old_line: int | None = None
    for line in fix_diff.splitlines():
        if line.startswith("diff --git "):
            parts = line.split()
            current = None
            old_line = None
            if parts and parts[-1].startswith("b/"):
                current = parts[-1][2:]
            continue
        if line.startswith("+++ "):
            name = line[4:].strip()
            if name.startswith("b/"):
                name = name[2:]
            if name != "/dev/null":
                current = name
            continue
        match = _HUNK.match(line)
        if match:
            old_line = int(match.group(1))
        elif current and old_line is not None and not _is_test_path(current):
            if line.startswith("-"):
                ranges.setdefault(current, []).append((old_line, old_line + 1))
                old_line += 1
            elif line.startswith("+"):
                # An insertion maps to the preceding line in the buggy tree.
                # This avoids attributing a change to a neighbouring function
                # merely because it occurs in diff context.
                anchor = max(1, old_line - 1)
                ranges.setdefault(current, []).append((anchor, anchor + 1))
            elif line.startswith(" "):
                old_line += 1
    return ranges


def _ctags(path: Path) -> list[tuple[str, int, int]]:
    proc = subprocess.run(
        [
            "ctags",
            "--languages=C,C++",
            "--kinds-C++=f",
            "--kinds-C=f",
            "--fields=+ne",
            "--output-format=json",
            "-f",
            "-",
            str(path),
        ],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        check=False,
        text=True,
    )
    found: list[tuple[str, int, int]] = []
    for line in proc.stdout.splitlines():
        line = line.strip()
        if not line.startswith("{"):
            continue
        try:
            item = json.loads(line)
        except json.JSONDecodeError:
            continue
        if item.get("_type") == "ptag":
            continue
        name = item.get("name")
        start = item.get("line")
        if not isinstance(name, str) or start is None:
            continue
        try:
            start_line = int(start)
            end_line = int(item.get("end") if item.get("end") is not None else start)
        except (TypeError, ValueError):
            continue
        found.append((name, start_line, end_line))
    return found


def _overlaps(start: int, end: int, lo: int, hi: int) -> bool:
    return start < hi and end >= lo


def changed_functions(buggy_repo: Path, fix_diff: str) -> list[FuncRange]:
    buggy_repo = Path(buggy_repo)
    selected: list[FuncRange] = []
    seen: set[tuple[str, str, int, int]] = set()
    for rel, hunks in _diff_ranges(fix_diff).items():
        path = buggy_repo / rel
        if not path.is_file():
            continue
        for name, start, end in _ctags(path):
            if not any(_overlaps(start, end, lo, hi) for lo, hi in hunks):
                continue
            key = (name, rel, start, end)
            if key in seen:
                continue
            seen.add(key)
            selected.append(FuncRange(name, rel, start, end))
    selected.sort(key=lambda item: (item.file, item.start, item.name))
    return selected


def _hit(function: str, file: str, via: str, evidence: str) -> dict:
    return {"function": function, "file": file, "via": via, "evidence": evidence}


def align(
    evidence_frames: list[Frame],
    coverage_hits: list[FuncRange] | None,
    changed: list[FuncRange],
    repo_root: str,
) -> Alignment:
    """Score frames, or coverage when a bundle has no stacks.

    ``coverage_hits is None`` with no frames means the coverage run timed out
    (or never produced a profile). Strict and relaxed are then false.
    """
    if not evidence_frames and coverage_hits is None:
        return Alignment(False, False, True, [])

    changed_files = {_norm(item.file, repo_root) for item in changed}
    hits: list[dict] = []
    relaxed = False

    if evidence_frames:
        for frame in evidence_frames:
            rel = _norm(frame.file, repo_root)
            if rel in changed_files:
                relaxed = True
            for fn in changed:
                if _norm(fn.file, repo_root) != rel:
                    continue
                if fn.start <= frame.line <= fn.end:
                    hits.append(
                        _hit(
                            fn.name,
                            rel,
                            "frame",
                            f"{rel}:{frame.line} {frame.function}",
                        )
                    )
                    break
        return Alignment(bool(hits), relaxed, False, hits)

    assert coverage_hits is not None
    for hit in coverage_hits:
        rel = _norm(hit.file, repo_root)
        if rel in changed_files:
            relaxed = True
        for fn in changed:
            if _norm(fn.file, repo_root) != rel:
                continue
            same_name = hit.name == fn.name or hit.name.endswith("::" + fn.name)
            if _overlaps(hit.start, hit.end, fn.start, fn.end + 1) or same_name:
                hits.append(_hit(fn.name, rel, "coverage", f"{rel}:{hit.start} {hit.name}"))
                break
    return Alignment(bool(hits), relaxed, False, hits)
