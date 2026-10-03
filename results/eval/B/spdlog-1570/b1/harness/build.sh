#!/usr/bin/env bash
set -euo pipefail

mkdir -p "$PS_OUT"

"$PS_CXX" -std=c++11 \
    -I"$PS_REPO/include" \
    -I"$PS_INCLUDE" \
    $PS_CXXFLAGS \
    "$PS_REPO/proofsmith_harness/harness.cpp" \
    -L"$PS_BUILD_DIR" -lspdlog \
    $PS_LDFLAGS \
    -pthread \
    -o "$PS_OUT/harness"
