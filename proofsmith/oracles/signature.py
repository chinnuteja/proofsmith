"""Parse sanitizer, assertion, and crash output into a stable signature."""

from __future__ import annotations

import re
import signal
from dataclasses import dataclass
from pathlib import Path

_CHECK = re.compile(r"PROOFSMITH_CHECK_FAILED (\S+):(\d+):")
_GLIBC_ASSERT = re.compile(r"Assertion .+ failed")
_FILE_LINE = re.compile(r"(\S+):(\d+):")
_ASAN = re.compile(r"ERROR: AddressSanitizer: ([a-z-]+)")
_UBSAN = re.compile(r"runtime error: ([^:\n]+)")
_TSAN = re.compile(r"WARNING: ThreadSanitizer: ([^(\n]+)")
_FRAME = re.compile(
    r"^\s*#(\d+)\s+(?:0x[0-9a-fA-F]+\s+in\s+)?(.+?)\s+(/[^\s:]+):(\d+)(?::\d+)?(?:\s+\(.*\))?\s*$"
)
_LAMBDA = re.compile(r"\$_\d+")


@dataclass
class Frame:
    index: int
    function: str
    file: str
    line: int


@dataclass
class Evidence:
    kind: str
    frames: list[Frame]
    app_frames: list[Frame]
    signature: str


def _slug(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", text.strip().lower()).strip("-")


def normalize_function(name: str) -> str:
    if name.endswith(" const"):
        name = name[: -len(" const")]
    if "operator()" in name:
        index = name.find("operator()")
        name = name[: index + len("operator()")]
    else:
        paren = name.find("(")
        if paren != -1:
            name = name[:paren]
    prefix = "(anonymous namespace)::"
    if name.startswith(prefix):
        name = name[len(prefix) :]
    return _LAMBDA.sub("$_", name)


def _signal_name(code: int) -> str:
    sig = -code if code < 0 else code - 128
    try:
        return signal.Signals(sig).name
    except ValueError:
        return f"SIG{sig}"


def _kind(output: str, exit_code: int, timed_out: bool) -> tuple[str, str | None, int | None]:
    check = _CHECK.search(output)
    if check:
        return "assert", check.group(1), int(check.group(2))
    if _GLIBC_ASSERT.search(output):
        where = _FILE_LINE.search(output)
        if where:
            return "assert", where.group(1), int(where.group(2))
        return "assert", None, None
    asan = _ASAN.search(output)
    if asan:
        return f"asan:{asan.group(1)}", None, None
    ubsan = _UBSAN.search(output)
    if ubsan:
        return f"ubsan:{_slug(ubsan.group(1))}", None, None
    tsan = _TSAN.search(output)
    if tsan:
        return f"tsan:{_slug(tsan.group(1))}", None, None
    if timed_out:
        return "timeout", None, None
    if exit_code < 0 or 128 < exit_code < 160:
        return f"crash:{_signal_name(exit_code)}", None, None
    if exit_code != 0:
        return f"exit:{exit_code}", None, None
    return "none", None, None


def _parse_frames(output: str) -> list[Frame]:
    frames: list[Frame] = []
    for line in output.splitlines():
        match = _FRAME.match(line)
        if not match:
            continue
        frames.append(
            Frame(
                index=int(match.group(1)),
                function=match.group(2).strip(),
                file=match.group(3),
                line=int(match.group(4)),
            )
        )
    return frames


def _is_app_frame(path: str, repo_root: str) -> bool:
    try:
        rel = Path(path).resolve().relative_to(Path(repo_root).resolve())
    except ValueError:
        return False
    return not rel.parts or rel.parts[0] != "proofsmith_harness"


def _relpath(path: str, repo_root: str) -> str:
    try:
        return Path(path).resolve().relative_to(Path(repo_root).resolve()).as_posix()
    except ValueError:
        return Path(path).name


def parse_evidence(output: str, exit_code: int, timed_out: bool, repo_root: str) -> Evidence:
    kind, assert_file, assert_line = _kind(output, exit_code, timed_out)
    frames = _parse_frames(output)
    if kind == "assert" and assert_file and assert_line is not None and not frames:
        frames = [Frame(index=0, function="PS_CHECK", file=assert_file, line=assert_line)]
    app_frames = [frame for frame in frames if _is_app_frame(frame.file, repo_root)]
    if kind == "assert" and assert_file and assert_line is not None:
        signature = f"assert|{_relpath(assert_file, repo_root)}:{assert_line}"
    elif kind.startswith(("asan:", "ubsan:", "tsan:")):
        parts = [
            f"{normalize_function(frame.function)}@{_relpath(frame.file, repo_root)}"
            for frame in app_frames[:3]
        ]
        signature = kind + "|" + "|".join(parts) if parts else kind
    else:
        signature = kind
    return Evidence(kind=kind, frames=frames, app_frames=app_frames, signature=signature)
