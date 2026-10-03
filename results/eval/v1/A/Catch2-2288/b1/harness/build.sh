#!/usr/bin/env bash
set -euo pipefail

mkdir -p "$PS_OUT"

"$PS_CXX" -std=c++11 -I"$PS_REPO/single_include" \
    $PS_CXXFLAGS \
    "$PS_REPO/proofsmith_harness/main.cpp" \
    $PS_LDFLAGS \
    -o "$PS_OUT/harness"
