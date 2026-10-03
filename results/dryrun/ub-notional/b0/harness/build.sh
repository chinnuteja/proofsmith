#!/usr/bin/env bash
set -euo pipefail

mkdir -p "$PS_OUT"

"$PS_CXX" $PS_CXXFLAGS \
  -I"$PS_REPO" \
  -I"$PS_INCLUDE" \
  "$PS_REPO/pricing.cpp" \
  "$PS_REPO/proofsmith_harness/main.cpp" \
  $PS_LDFLAGS \
  -o "$PS_OUT/harness"
