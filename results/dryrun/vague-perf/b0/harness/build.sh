#!/usr/bin/env bash
set -euo pipefail

mkdir -p "$PS_OUT"

"$PS_CXX" \
  -std=c++17 \
  $PS_CXXFLAGS \
  -I"$PS_REPO" \
  "$PS_REPO/proofsmith_harness/harness.cpp" \
  "$PS_REPO/match.cpp" \
  -o "$PS_OUT/harness" \
  $PS_LDFLAGS
