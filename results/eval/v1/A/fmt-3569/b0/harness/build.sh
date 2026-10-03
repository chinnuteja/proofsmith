#!/usr/bin/env bash
set -euo pipefail

REPO="${PS_REPO:-$(pwd)}"
OUT="${PS_OUT:-.}"
CXX="${PS_CXX:-clang++}"

mkdir -p "$OUT"

# Compile the reproducer against the repository's current fmt headers.
# std::vector<bool>::reference is not formattable in the buggy version, so
# this compilation fails; once fixed it succeeds.
if "$CXX" -std=c++11 -DFMT_HEADER_ONLY ${PS_CXXFLAGS:-} \
    -I"$REPO/include" -fsyntax-only "$REPO/proofsmith_harness/repro.cpp" \
    >/dev/null 2>&1; then
  define="REPRO_COMPILES=1"
else
  define="REPRO_COMPILES=0"
fi

"$CXX" -std=c++11 ${PS_CXXFLAGS:-} -D"$define" \
    "$REPO/proofsmith_harness/harness.cpp" -o "$OUT/harness"
