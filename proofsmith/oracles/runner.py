"""Run a binary n times and attach parsed evidence."""

from __future__ import annotations

import os
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path

from proofsmith.oracles.signature import Evidence, parse_evidence
from proofsmith.oracles.variants import VARIANTS

_KEEP = ("PATH", "HOME", "LANG", "LC_ALL", "USER", "LOGNAME", "LD_LIBRARY_PATH", "TMPDIR")


@dataclass
class RunResult:
    index: int
    exit_code: int
    timed_out: bool
    duration_s: float
    evidence: Evidence
    output_path: str


def variant_env(variant: str) -> dict[str, str]:
    env = {key: os.environ[key] for key in _KEEP if key in os.environ}
    env.setdefault("LANG", "C.UTF-8")
    env.update(VARIANTS[variant].env)
    profile = env.get("LLVM_PROFILE_FILE")
    if profile == "<set at runtime>":
        env["LLVM_PROFILE_FILE"] = "default.profraw"
    return env


def run_n(
    binary: Path,
    variant: str,
    n: int,
    timeout_s: int,
    cwd: Path,
    repo_root: str,
    log_dir: Path,
) -> list[RunResult]:
    log_dir.mkdir(parents=True, exist_ok=True)
    env = variant_env(variant)
    results: list[RunResult] = []
    for index in range(n):
        log_path = log_dir / f"run-{index:02d}.log"
        started = time.monotonic()
        timed_out = False
        try:
            proc = subprocess.run(
                [str(binary)],
                cwd=cwd,
                env=env,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                timeout=timeout_s,
                check=False,
                start_new_session=True,
            )
            output = proc.stdout.decode("utf-8", errors="replace")
            code = proc.returncode
        except subprocess.TimeoutExpired as exc:
            timed_out = True
            raw = exc.stdout or b""
            if isinstance(raw, str):
                output = raw
            else:
                output = raw.decode("utf-8", errors="replace")
            output += "\nTIMEOUT\n"
            code = -1
        duration = time.monotonic() - started
        output = output.replace("\r\n", "\n")
        log_path.write_text(output, encoding="utf-8", newline="\n")
        evidence = parse_evidence(output, code, timed_out, repo_root)
        results.append(
            RunResult(
                index=index,
                exit_code=code,
                timed_out=timed_out,
                duration_s=duration,
                evidence=evidence,
                output_path=str(log_path),
            )
        )
    return results
