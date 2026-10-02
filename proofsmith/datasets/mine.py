"""Track B candidate mining from local git history."""

from __future__ import annotations

import json
import re
import subprocess
from dataclasses import asdict, dataclass, field
from pathlib import Path

from proofsmith.config import REPO, WORK

GREP = (
    "data race|tsan|threadsanitizer|use[- ]after[- ]free|"
    "heap-use-after-free|deadlock|lock[- ]order|race condition|dangling"
)

REPOS = [
    "https://github.com/cameron314/concurrentqueue",
    "https://github.com/gabime/spdlog",
    "https://github.com/google/leveldb",
    "https://github.com/taskflow/taskflow",
    "https://github.com/yhirose/cpp-httplib",
    "https://github.com/libuv/libuv",
    "https://github.com/uxlfoundation/oneTBB",
    "https://github.com/redis/redis",
    "https://github.com/facebook/rocksdb",
]

SOURCE_EXTS = {
    ".c",
    ".cc",
    ".cpp",
    ".cxx",
    ".h",
    ".hh",
    ".hpp",
    ".hxx",
    ".ipp",
    ".inl",
}

_TEST_PARTS = {
    "test",
    "tests",
    "testing",
    "bench",
    "benchmark",
    "benchmarks",
    "example",
    "examples",
    "doc",
    "docs",
    "fuzz",
    "fuzzing",
    "third_party",
    "third-party",
    "googletest",
    "gtest",
}

_REF_RE = re.compile(
    r"(?:https://github\.com/[^/\s]+/[^/\s]+/(?:issues|pull)/(\d+))"
    r"|(?:(?:fix(?:e[sd])?|clos(?:e[sd])?|resolv(?:e[sd])?)\s+#(\d+))"
    r"|\(#(\d+)\)",
    re.IGNORECASE,
)


@dataclass
class Candidate:
    repo: str
    sha: str
    parent: str
    subject: str
    files_changed: int
    lines_changed: int
    pr_url: str | None = None
    issue_url: str | None = None
    org: str = ""
    name: str = ""
    committed: int = 0
    parents: list[str] = field(default_factory=list)
    files: list[str] = field(default_factory=list)
    refs: list[int] = field(default_factory=list)
    reasons: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return asdict(self)


def repo_slug(url: str) -> str:
    parts = url.rstrip("/").split("/")
    name = parts[-1].removesuffix(".git")
    org = parts[-2]
    return f"{org}__{name}"


def mirror_path(url: str) -> Path:
    return WORK / "repos" / repo_slug(url)


def org_repo(url: str) -> tuple[str, str]:
    parts = url.rstrip("/").split("/")
    return parts[-2], parts[-1].removesuffix(".git")


def is_test_path(path: str) -> bool:
    parts = path.replace("\\", "/").split("/")
    lowered = [part.lower() for part in parts]
    for part in lowered:
        if part in _TEST_PARTS or part.startswith("test_") or part.endswith("_test"):
            return True
    name = lowered[-1] if lowered else ""
    stems = (
        "test",
        "_test.",
        "_tests.",
        "tests.",
        "bench",
        "benchmark",
        "fuzz",
    )
    return name.startswith("test") or any(token in name for token in stems)


def is_source_path(path: str) -> bool:
    return Path(path).suffix.lower() in SOURCE_EXTS and not is_test_path(path)


def _run(cmd: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        check=False,
        text=True,
    )


def clone_mirror(url: str) -> Path:
    dest = mirror_path(url)
    if (dest / ".git").exists():
        return dest
    dest.parent.mkdir(parents=True, exist_ok=True)
    print(f"CLONE {url}", flush=True)
    proc = _run(["git", "clone", "--filter=blob:none", url, str(dest)])
    if proc.returncode != 0:
        raise RuntimeError(proc.stdout)
    print(f"CLONED {dest}", flush=True)
    return dest


def confirm_remote(url: str) -> bool:
    proc = _run(["git", "ls-remote", url, "HEAD"])
    ok = proc.returncode == 0 and bool(proc.stdout.strip())
    print(f"REMOTE {'ok' if ok else 'FAIL'} {url}", flush=True)
    if not ok:
        print(proc.stdout[-500:], flush=True)
    return ok


def _refs(text: str) -> list[int]:
    found: list[int] = []
    for match in _REF_RE.finditer(text):
        number = next(group for group in match.groups() if group)
        value = int(number)
        if value not in found:
            found.append(value)
    return found


def _urls_from_message(org: str, name: str, text: str) -> tuple[str | None, str | None]:
    issue = None
    pull = None
    for match in re.finditer(r"https://github\.com/[^/\s]+/[^/\s]+/(issues|pull)/(\d+)", text):
        url = match.group(0)
        if match.group(1) == "issues" and issue is None:
            issue = url
        elif match.group(1) == "pull" and pull is None:
            pull = url
    return issue, pull


def _size_reasons(files: list[str], lines: int) -> list[str]:
    reasons: list[str] = []
    if not files:
        reasons.append("no non-test source files")
    if len(files) > 5:
        reasons.append(f"{len(files)} non-test source files")
    if lines > 200:
        reasons.append(f"{lines} changed lines")
    return reasons


def _parse_log(org: str, name: str, payload: str) -> list[Candidate]:
    repo = f"{org}/{name}"
    found: list[Candidate] = []
    current: dict | None = None

    def finish(item: dict) -> None:
        files = [row[2] for row in item["rows"] if is_source_path(row[2])]
        lines = 0
        for added, deleted, _path in item["rows"]:
            if added.isdigit():
                lines += int(added)
            if deleted.isdigit():
                lines += int(deleted)
        subject = item["subject"]
        issue, pull = _urls_from_message(org, name, subject)
        found.append(
            Candidate(
                repo=repo,
                sha=item["sha"],
                parent=item["parents"][0] if item["parents"] else "",
                subject=subject,
                files_changed=len(files),
                lines_changed=lines,
                pr_url=pull,
                issue_url=issue,
                org=org,
                name=name,
                committed=item["committed"],
                parents=item["parents"],
                files=files,
                refs=_refs(subject),
                reasons=_size_reasons(files, lines),
            )
        )

    for line in payload.splitlines():
        if line.startswith("COMMIT\x1f"):
            if current is not None:
                finish(current)
            parts = line.split("\x1f")
            if len(parts) < 5:
                current = None
                continue
            parents = [part for part in parts[2].split() if part]
            try:
                committed = int(parts[3])
            except ValueError:
                committed = 0
            current = {
                "sha": parts[1],
                "parents": parents,
                "committed": committed,
                "subject": parts[4],
                "rows": [],
            }
            continue
        if current is None or not line.strip():
            continue
        bits = line.split("\t")
        if len(bits) >= 3:
            current["rows"].append((bits[0], bits[1], bits[-1]))
    if current is not None:
        finish(current)
    return found


def mine(repo_url: str, since: str) -> list[Candidate]:
    """Search one repository for lifetime and concurrency fix candidates."""
    org, name = org_repo(repo_url)
    dest = clone_mirror(repo_url)
    cmd = [
        "git",
        "-C",
        str(dest),
        "log",
        "--all",
        "-i",
        "-E",
        f"--grep={GREP}",
        "--pretty=tformat:COMMIT%x1f%H%x1f%P%x1f%ct%x1f%s",
        "--numstat",
    ]
    if since:
        cmd.append(f"--since={since}")
    print(f"SCAN {org}/{name}", flush=True)
    proc = _run(cmd)
    if proc.returncode != 0:
        raise RuntimeError(proc.stdout[-2000:])
    found = _parse_log(org, name, proc.stdout)
    print(f"REPO_DONE {org}/{name} candidates={len(found)}", flush=True)
    return found


class RateLimitError(RuntimeError):
    pass


def github_get(path: str) -> dict:
    """Unauthenticated GitHub REST GET. Raises RateLimitError when the budget is spent."""
    url = "https://api.github.com/" + path.lstrip("/")
    proc = _run(
        [
            "curl",
            "-sS",
            "-D",
            "-",
            "-H",
            "Accept: application/vnd.github+json",
            "-H",
            "User-Agent: proofsmith",
            "-o",
            "/tmp/proofsmith-gh-body.json",
            url,
        ]
    )
    if proc.returncode != 0:
        raise RuntimeError(proc.stdout[-500:])
    header, _, _rest = proc.stdout.partition("\r\n\r\n")
    if not header:
        header = proc.stdout
    status = 0
    remaining = None
    for line in header.splitlines():
        if line.startswith("HTTP/"):
            bits = line.split()
            if len(bits) >= 2 and bits[1].isdigit():
                status = int(bits[1])
        lower = line.lower()
        if lower.startswith("x-ratelimit-remaining:"):
            remaining = int(line.split(":", 1)[1].strip())
    body = Path("/tmp/proofsmith-gh-body.json").read_text(encoding="utf-8")
    if status == 403 and (remaining == 0 or "rate limit" in body.lower()):
        print(f"RATE_LIMIT remaining={remaining}", flush=True)
        raise RateLimitError(body[:500])
    if status != 200:
        raise RuntimeError(f"GitHub {status} for {path}: {body[:400]}")
    print(f"API {status} remaining={remaining} {path}", flush=True)
    return json.loads(body)


def write_candidates(path: Path, rows: list[Candidate]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = [json.dumps(row.to_dict(), ensure_ascii=False) for row in rows]
    text = "\n".join(lines)
    if text:
        text += "\n"
    path.write_text(text, encoding="utf-8", newline="\n")


def load_candidates(path: Path | None = None) -> list[Candidate]:
    path = path or (REPO / "data" / "trackB" / "candidates.jsonl")
    if not path.is_file():
        return []
    rows: list[Candidate] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        raw = json.loads(line)
        rows.append(Candidate(**raw))
    return rows


def main(argv: list[str] | None = None) -> int:
    import argparse

    parser = argparse.ArgumentParser(prog="trackb-mine")
    parser.add_argument("--since", default="")
    parser.add_argument("--repo", action="append", default=[])
    parser.add_argument("--out", default="")
    args = parser.parse_args(argv)
    selected = args.repo or list(REPOS)
    out = Path(args.out) if args.out else REPO / "data" / "trackB" / "candidates.jsonl"
    scan_dir = REPO / "data" / "trackB" / "scan"
    scan_dir.mkdir(parents=True, exist_ok=True)

    if "uxlfoundation/oneTBB" in " ".join(selected) or any(
        item.rstrip("/").endswith("uxlfoundation/oneTBB") for item in selected
    ):
        confirm_remote("https://github.com/uxlfoundation/oneTBB")

    combined: list[Candidate] = []
    if out.is_file() and args.repo:
        combined = load_candidates(out)
        keep = {org_repo(url) for url in selected}
        combined = [row for row in combined if (row.org, row.name) not in keep]

    for url in selected:
        org, name = org_repo(url)
        try:
            rows = mine(url, args.since)
        except Exception as exc:
            print(f"REPO_FAIL {org}/{name} {exc}", flush=True)
            continue
        part = scan_dir / f"{org}__{name}.jsonl"
        write_candidates(part, rows)
        combined.extend(rows)
        write_candidates(out, combined)
        eligible = [row for row in rows if not row.reasons]
        eligible.sort(key=lambda row: (-row.committed, row.lines_changed))
        print(f"SHORTLIST {org}/{name} {len(eligible)}", flush=True)
        for row in eligible:
            print(
                f"SHORT {row.repo} {row.committed} {row.sha} "
                f"files={row.files_changed} lines={row.lines_changed} {row.subject[:160]}",
                flush=True,
            )
    print(f"SCAN_DONE {len(combined)} -> {out}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
