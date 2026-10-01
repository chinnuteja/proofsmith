"""Phase 0 config and variant contracts."""

from __future__ import annotations

import os
from pathlib import Path

import proofsmith.config as config
from proofsmith.oracles.variants import VARIANTS


def test_constants_match_global_constraints():
    assert config.RUNTIME_N == 10
    assert config.RUNTIME_K == 8
    assert config.EVAL_N == 20
    assert config.EVAL_BUGGY_K == 16
    assert config.EVAL_FIXED_MAX_FAILS == 0
    assert config.RUN_TIMEOUT_S == 60
    assert config.SIGNATURE_FRAMES == 3
    assert config.MAX_STEPS == 50
    assert config.MAX_TOTAL_TOKENS == 500000
    assert config.MAX_WALL_S == 1800
    assert config.EVAL_MODEL == "deepseek-v4-pro"
    assert config.DEV_MODEL == "deepseek-flash"
    assert config.API_BASE == "https://api.deepseek.com"
    source = (config.REPO / "proofsmith" / "config.py").read_text(encoding="utf-8")
    assert 'os.environ.get("PROOFSMITH_MAX_USD", "4.50")' in source
    assert config.MAX_USD == float(os.environ.get("PROOFSMITH_MAX_USD", "4.50"))
    assert config.WORK == Path.home() / "psw"
    assert config.SITE == config.REPO / "site"
    assert config.RESULTS == config.REPO / "results"
    assert config.RUNS == config.REPO / "runs"
    assert (config.REPO / "pyproject.toml").is_file()


def test_variants():
    assert set(VARIANTS) == {"plain", "asan_ubsan", "tsan", "coverage"}
    assert "address" in VARIANTS["asan_ubsan"].cxxflags
    assert "thread" not in VARIANTS["asan_ubsan"].cxxflags
    assert "thread" in VARIANTS["tsan"].cxxflags
    assert "address" not in VARIANTS["tsan"].cxxflags
    assert VARIANTS["plain"].cxxflags == "-g -O1 -fno-omit-frame-pointer"
    assert VARIANTS["asan_ubsan"].ldflags == "-fsanitize=address,undefined"
    assert VARIANTS["tsan"].ldflags == "-fsanitize=thread"
    assert VARIANTS["coverage"].cxxflags == "-g -O0 -fprofile-instr-generate -fcoverage-mapping"
    assert VARIANTS["coverage"].env["LLVM_PROFILE_FILE"] == "<set at runtime>"
    assert "exitcode=23" in VARIANTS["asan_ubsan"].env["ASAN_OPTIONS"]
    assert "exitcode=24" in VARIANTS["asan_ubsan"].env["UBSAN_OPTIONS"]
    assert VARIANTS["asan_ubsan"].env["ASAN_SYMBOLIZER_PATH"] == "/usr/bin/llvm-symbolizer"
    assert "exitcode=66" in VARIANTS["tsan"].env["TSAN_OPTIONS"]
    assert "external_symbolizer_path=/usr/bin/llvm-symbolizer" in VARIANTS["tsan"].env["TSAN_OPTIONS"]


def test_env_is_gitignored():
    text = (config.REPO / ".gitignore").read_text(encoding="utf-8")
    names = {line.strip() for line in text.splitlines() if line.strip() and not line.startswith("#")}
    assert ".env" in names
