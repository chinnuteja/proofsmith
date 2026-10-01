"""History-free, network-isolated snapshot of a source tree."""

from __future__ import annotations

import os
import shutil
import signal
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path

from proofsmith.config import WORK

_HEAD = 8000
_TAIL = 12000


@dataclass
class ExecResult:
    exit_code: int
    output: str
    timed_out: bool
    duration_s: float


def truncate_output(text: str) -> str:
    if len(text) <= _HEAD + _TAIL:
        return text
    omitted = len(text) - _HEAD - _TAIL
    return text[:_HEAD] + f"\n[... {omitted} chars truncated ...]\n" + text[-_TAIL:]


def _git(repo: Path, args: list[str]) -> subprocess.CompletedProcess[str]:
    cmd = [
        "git",
        "-c",
        "user.email=proofsmith@localhost",
        "-c",
        "user.name=proofsmith",
        *args,
    ]
    env = os.environ.copy()
    env["GIT_AUTHOR_NAME"] = "proofsmith"
    env["GIT_AUTHOR_EMAIL"] = "proofsmith@localhost"
    env["GIT_COMMITTER_NAME"] = "proofsmith"
    env["GIT_COMMITTER_EMAIL"] = "proofsmith@localhost"
    return subprocess.run(
        cmd,
        cwd=repo,
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        check=False,
        text=True,
    )


class Sandbox:
    def __init__(self, repo: Path, run_id: str):
        self.repo = Path(repo)
        self.run_id = run_id

    @classmethod
    def create(cls, src_repo: Path, run_id: str) -> Sandbox:
        root = WORK / "sandboxes" / run_id
        if root.exists():
            shutil.rmtree(root)
        repo = root / "repo"
        shutil.copytree(src_repo, repo, ignore=shutil.ignore_patterns(".git"))
        init = _git(repo, ["init", "-q"])
        if init.returncode != 0:
            raise RuntimeError(init.stdout)
        add = _git(repo, ["add", "-A"])
        if add.returncode != 0:
            raise RuntimeError(add.stdout)
        commit = _git(repo, ["commit", "-qm", "snapshot"])
        if commit.returncode != 0:
            raise RuntimeError(commit.stdout)
        (repo / "proofsmith_harness").mkdir(exist_ok=True)
        return cls(repo, run_id)

    def exec(self, cmd: str, timeout_s: int) -> ExecResult:
        script = self.repo.parent / "cmd.sh"
        script.write_text(cmd if cmd.endswith("\n") else cmd + "\n", encoding="utf-8", newline="\n")
        inner = (
            "ip link set lo up 2>/dev/null; "
            f"cd { _shell_quote(str(self.repo)) } && bash { _shell_quote(str(script)) }"
        )
        started = time.monotonic()
        proc = subprocess.Popen(
            ["unshare", "-rn", "bash", "-c", inner],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            start_new_session=True,
        )
        timed_out = False
        try:
            raw, _ = proc.communicate(timeout=timeout_s)
            code = proc.returncode if proc.returncode is not None else -1
        except subprocess.TimeoutExpired:
            timed_out = True
            _kill_group(proc.pid)
            raw, _ = proc.communicate()
            code = -1
        duration = time.monotonic() - started
        text = (raw or b"").decode("utf-8", errors="replace").replace("\r\n", "\n")
        return ExecResult(code, truncate_output(text), timed_out, duration)

    def changed_paths(self) -> list[str]:
        proc = _git(self.repo, ["status", "--porcelain"])
        paths: list[str] = []
        for line in proc.stdout.splitlines():
            if len(line) < 4:
                continue
            path = line[3:].strip()
            if " -> " in path:
                path = path.split(" -> ", 1)[1].strip()
            if len(path) >= 2 and path[0] == '"' and path[-1] == '"':
                path = path[1:-1]
            paths.append(path)
        return paths

    def illegal_changes(self) -> list[str]:
        bad: list[str] = []
        for path in self.changed_paths():
            norm = path.replace("\\", "/").rstrip("/")
            if norm == "proofsmith_harness" or norm.startswith("proofsmith_harness/"):
                continue
            bad.append(path)
        return bad

    def destroy(self) -> None:
        root = WORK / "sandboxes" / self.run_id
        if root.exists():
            shutil.rmtree(root)


def _shell_quote(text: str) -> str:
    return "'" + text.replace("'", "'\"'\"'") + "'"


def _kill_group(pid: int) -> None:
    try:
        os.killpg(pid, signal.SIGKILL)
    except ProcessLookupError:
        return
