#!/usr/bin/env bash
set -euo pipefail

mkdir -p "$PS_OUT"

"${PS_CXX:-clang++}" \
  -std=c++17 \
  -I"$PS_REPO" \
  $PS_CXXFLAGS \
  "$PS_REPO/proofsmith_harness/repro.cpp" \
  "$PS_REPO/ticks.cpp" \
  -o "$PS_OUT/harness" \
  $PS_LDFLAGS
