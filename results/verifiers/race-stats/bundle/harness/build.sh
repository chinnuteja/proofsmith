#!/usr/bin/env bash
set -euo pipefail

mkdir -p "$PS_OUT"

"$PS_CXX" \
  $PS_CXXFLAGS \
  -I"$PS_REPO" \
  -I"$PS_INCLUDE" \
  "$PS_REPO/proofsmith_harness/harness.cpp" \
  "$PS_BUILD_DIR/libcore.a" \
  -pthread \
  $PS_LDFLAGS \
  -o "$PS_OUT/harness"
