#!/usr/bin/env bash
set -euo pipefail

mkdir -p "$PS_OUT"

"$PS_CXX" -std=c++17 -I"$PS_REPO" $PS_CXXFLAGS \
  "$PS_REPO/proofsmith_harness/harness.cpp" \
  "$PS_REPO/price_cache.cpp" \
  $PS_LDFLAGS -o "$PS_OUT/harness"
