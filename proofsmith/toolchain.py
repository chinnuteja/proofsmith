"""Toolchain doctor: compile and run the Phase 0 sanitizer probes."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
from dataclasses import asdict, dataclass
from pathlib import Path

from proofsmith.config import REPO, RESULTS, RUN_TIMEOUT_S, WORK
from proofsmith.oracles.signature import parse_evidence
from proofsmith.oracles.variants import VARIANTS

PROBES: list[tuple[str, str, str]] = [
    ("heap_overflow", "asan_ubsan", "asan:heap-buffer-overflow"),
    ("use_after_free", "asan_ubsan", "asan:heap-use-after-free"),
    ("signed_overflow", "asan_ubsan", "ubsan:signed-integer-overflow"),
    ("data_race", "tsan", "tsan:data-race"),
    ("lock_order", "tsan", "tsan:lock-order-inversion"),
    ("check_fail", "plain", "assert"),
]


@dataclass
class ProbeResult:
    name: str
    variant: str
    expected_kind: str
    observed_kind: str
    ok: bool
    output_path: str


def _child_env(variant_name: str) -> dict[str, str]:
    keep = ("PATH", "HOME", "LANG", "LC_ALL", "USER", "LOGNAME", "LD_LIBRARY_PATH", "TMPDIR")
    env = {key: os.environ[key] for key in keep if key in os.environ}
    env.setdefault("LANG", "C.UTF-8")
    env.update(VARIANTS[variant_name].env)
    return env


def _compile(src: Path, binary: Path, variant_name: str, include: Path) -> None:
    variant = VARIANTS[variant_name]
    cmd = [
        "clang++",
        "-std=c++17",
        *variant.cxxflags.split(),
        f"-I{include}",
        str(src),
        "-o",
        str(binary),
        *variant.ldflags.split(),
        "-pthread",
    ]
    proc = subprocess.run(
        cmd,
        cwd=src.parent,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        check=False,
    )
    if proc.returncode != 0:
        text = proc.stdout.decode("utf-8", errors="replace")
        raise RuntimeError(text)


def doctor() -> list[ProbeResult]:
    probe_dir = WORK / "probes"
    if probe_dir.exists():
        shutil.rmtree(probe_dir)
    probe_dir.mkdir(parents=True)
    header_src = REPO / "proofsmith" / "runtime" / "proofsmith_check.h"
    shutil.copy2(header_src, probe_dir / "proofsmith_check.h")
    fixture_dir = REPO / "tests" / "fixtures" / "sanitizer"
    fixture_dir.mkdir(parents=True, exist_ok=True)

    results: list[ProbeResult] = []
    for name, variant, expected in PROBES:
        src = probe_dir / f"{name}.cpp"
        shutil.copy2(REPO / "tests" / "probes" / f"{name}.cpp", src)
        binary = probe_dir / name
        rel = f"tests/fixtures/sanitizer/{name}.txt"
        dest = REPO / rel
        timed_out = False
        code = 1
        try:
            _compile(src, binary, variant, probe_dir)
            proc = subprocess.run(
                [str(binary)],
                cwd=probe_dir,
                env=_child_env(variant),
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                timeout=RUN_TIMEOUT_S,
                check=False,
            )
            output = proc.stdout.decode("utf-8", errors="replace")
            code = proc.returncode
        except subprocess.TimeoutExpired as exc:
            timed_out = True
            raw = exc.stdout or b""
            output = raw.decode("utf-8", errors="replace") + "\nTIMEOUT\n"
            code = -1
        except RuntimeError as exc:
            output = f"COMPILE FAILED\n{exc}\n"
        output = output.replace("\r\n", "\n")
        dest.write_text(output, encoding="utf-8", newline="\n")
        kind = parse_evidence(output, code, timed_out, str(probe_dir)).kind
        results.append(
            ProbeResult(
                name=name,
                variant=variant,
                expected_kind=expected,
                observed_kind=kind,
                ok=kind == expected,
                output_path=rel,
            )
        )
    return results


def clang_version_line() -> str:
    proc = subprocess.run(
        ["clang", "--version"],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        check=True,
    )
    return proc.stdout.decode("utf-8", errors="replace").splitlines()[0].strip()


def write_toolchain_json(results: list[ProbeResult] | None = None) -> Path:
    if results is None:
        results = doctor()
    RESULTS.mkdir(parents=True, exist_ok=True)
    payload = {
        "clang_version": clang_version_line(),
        "probes": [asdict(item) for item in results],
    }
    path = RESULTS / "toolchain.json"
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8", newline="\n")
    return path
