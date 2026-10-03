"""Compile proofsmith_harness/build.sh for one variant."""

from __future__ import annotations

import os
import subprocess
from dataclasses import dataclass
from pathlib import Path

from proofsmith.config import REPO
from proofsmith.oracles.builds import BuildResult
from proofsmith.oracles.variants import VARIANTS
from proofsmith.isolation import child_env, isolated_command


@dataclass
class HarnessBuild:
    ok: bool
    binary: Path | None
    log_path: Path


def compile_harness(repo: Path, build: BuildResult, variant: str, out_dir: Path) -> HarnessBuild:
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    log_path = out_dir / "harness-build.log"
    script = Path(repo) / "proofsmith_harness" / "build.sh"
    if not script.is_file():
        log_path.write_text("missing proofsmith_harness/build.sh\n", encoding="utf-8", newline="\n")
        return HarnessBuild(False, None, log_path)
    spec = VARIANTS[variant]
    env = child_env()
    env.update(
        {
            "PS_REPO": str(Path(repo).resolve()),
            "PS_BUILD_DIR": str(Path(build.build_dir).resolve()),
            "PS_COMPILE_COMMANDS": str(build.compile_commands.resolve()) if build.compile_commands else "",
            "PS_CC": "clang",
            "PS_CXX": "clang++",
            "PS_CXXFLAGS": spec.cxxflags,
            "PS_LDFLAGS": spec.ldflags,
            "PS_INCLUDE": str((REPO / "proofsmith" / "runtime").resolve()),
            "PS_OUT": str(out_dir.resolve()),
        }
    )
    try:
        proc = _compile(repo, build, out_dir, env)
    except subprocess.TimeoutExpired:
        log_path.write_text("harness build exceeded 120 seconds\n", encoding="utf-8")
        return HarnessBuild(False, None, log_path)
    log_path.write_text(proc.stdout, encoding="utf-8", newline="\n")
    binary = out_dir / "harness"
    if proc.returncode != 0 or not binary.is_file() or not os.access(binary, os.X_OK):
        return HarnessBuild(False, None, log_path)
    return HarnessBuild(True, binary, log_path)


def _compile(repo: Path, build: BuildResult, out_dir: Path, env: dict):
    return subprocess.run(
        isolated_command(["bash", "proofsmith_harness/build.sh"], Path(repo),
                         read=[build.build_dir.resolve(), REPO / "proofsmith/runtime"],
                         write=[Path(repo), out_dir]),
        cwd=repo,
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        check=False,
        text=True,
        timeout=120,
    )
