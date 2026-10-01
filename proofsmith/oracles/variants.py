"""Build and run variants. Flags and runtime env match the global constraints."""

from __future__ import annotations

from dataclasses import dataclass


BASE_CXXFLAGS = "-g -O1 -fno-omit-frame-pointer"

ASAN_UBSAN_SANITIZE = "-fsanitize=address,undefined"
TSAN_SANITIZE = "-fsanitize=thread"
COVERAGE_FLAGS = "-g -O0 -fprofile-instr-generate -fcoverage-mapping"


@dataclass(frozen=True)
class Variant:
    name: str
    cxxflags: str
    ldflags: str
    env: dict[str, str]


VARIANTS: dict[str, Variant] = {
    "plain": Variant(
        name="plain",
        cxxflags=BASE_CXXFLAGS,
        ldflags="",
        env={},
    ),
    "asan_ubsan": Variant(
        name="asan_ubsan",
        cxxflags=f"{BASE_CXXFLAGS} {ASAN_UBSAN_SANITIZE} -fno-sanitize-recover=undefined",
        ldflags=ASAN_UBSAN_SANITIZE,
        env={
            "ASAN_OPTIONS": (
                "halt_on_error=1:abort_on_error=0:detect_leaks=0:exitcode=23:"
                "symbolize=1:allocator_may_return_null=1"
            ),
            "UBSAN_OPTIONS": "halt_on_error=1:print_stacktrace=1:exitcode=24:symbolize=1",
            "ASAN_SYMBOLIZER_PATH": "/usr/bin/llvm-symbolizer",
        },
    ),
    "tsan": Variant(
        name="tsan",
        cxxflags=f"{BASE_CXXFLAGS} {TSAN_SANITIZE}",
        ldflags=TSAN_SANITIZE,
        env={
            "TSAN_OPTIONS": (
                "halt_on_error=1:exitcode=66:second_deadlock_stack=1:symbolize=1:"
                "external_symbolizer_path=/usr/bin/llvm-symbolizer"
            ),
        },
    ),
    "coverage": Variant(
        name="coverage",
        cxxflags=COVERAGE_FLAGS,
        ldflags="-fprofile-instr-generate -fcoverage-mapping",
        env={"LLVM_PROFILE_FILE": "<set at runtime>"},
    ),
}
