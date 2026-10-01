"""Network-isolated snapshot: one commit, loopback up, no outside writes."""

from __future__ import annotations

import os
import subprocess
from pathlib import Path

import pytest

from proofsmith.sandbox import Sandbox, truncate_output

pytestmark = pytest.mark.slow


def _git_env() -> dict[str, str]:
    env = os.environ.copy()
    env["GIT_AUTHOR_NAME"] = "proofsmith"
    env["GIT_AUTHOR_EMAIL"] = "proofsmith@localhost"
    env["GIT_COMMITTER_NAME"] = "proofsmith"
    env["GIT_COMMITTER_EMAIL"] = "proofsmith@localhost"
    return env


def _commit(repo: Path, message: str) -> None:
    env = _git_env()
    subprocess.run(["git", "add", "-A"], cwd=repo, check=True, env=env)
    subprocess.run(
        [
            "git",
            "-c",
            "user.email=proofsmith@localhost",
            "-c",
            "user.name=proofsmith",
            "commit",
            "-qm",
            message,
        ],
        cwd=repo,
        check=True,
        env=env,
    )


def test_truncate_keeps_head_and_tail():
    text = "H" * 8000 + "M" * 50 + "T" * 12000
    clipped = truncate_output(text)
    assert clipped.startswith("H" * 8000)
    assert clipped.endswith("T" * 12000)
    assert "[... 50 chars truncated ...]" in clipped
    assert truncate_output("short") == "short"


def test_sandbox_is_isolated(tmp_path: Path):
    src = tmp_path / "src"
    src.mkdir()
    (src / "order_book.cpp").write_text("int original;\n", encoding="utf-8")
    (src / "hello.txt").write_text("hi\n", encoding="utf-8")
    subprocess.run(["git", "init", "-q"], cwd=src, check=True)
    _commit(src, "SECRET-HISTORY")
    (src / "hello.txt").write_text("v2\n", encoding="utf-8")
    _commit(src, "second")

    sandbox = Sandbox.create(src, "phase2-sandbox-iso")
    try:
        count = subprocess.run(
            ["git", "-C", str(sandbox.repo), "rev-list", "--count", "HEAD"],
            check=True,
            capture_output=True,
            text=True,
        )
        assert count.stdout.strip() == "1"
        log = subprocess.run(
            ["git", "-C", str(sandbox.repo), "log", "--format=%s"],
            check=True,
            capture_output=True,
            text=True,
        )
        assert log.stdout.strip().splitlines() == ["snapshot"]
        assert "SECRET-HISTORY" not in log.stdout
        assert (sandbox.repo / "proofsmith_harness").is_dir()

        curl = sandbox.exec("curl -sS -m 5 https://example.com", 30)
        assert curl.exit_code != 0, curl.output[-500:]
        assert curl.timed_out is False

        loopback = sandbox.exec(
            """python3 - << 'PY'
import socket
s = socket.socket()
s.bind(("127.0.0.1", 0))
print("lo ok")
PY""",
            30,
        )
        assert loopback.exit_code == 0, loopback.output[-500:]
        assert "lo ok" in loopback.output

        sandbox.exec("printf 'hacked\\n' >> order_book.cpp", 30)
        illegal = sandbox.illegal_changes()
        assert any("order_book.cpp" in path for path in illegal), illegal

        sandbox.exec("mkdir -p proofsmith_harness && printf 'int y;\\n' > proofsmith_harness/x.cpp", 30)
        illegal = sandbox.illegal_changes()
        assert any("order_book.cpp" in path for path in illegal), illegal
        assert all("x.cpp" not in path for path in illegal), illegal

        timed = sandbox.exec("sleep 30", 2)
        assert timed.timed_out is True
    finally:
        sandbox.destroy()
