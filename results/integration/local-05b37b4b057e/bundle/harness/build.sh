#!/usr/bin/env bash
set -euo pipefail
mkdir -p "$PS_OUT"
# shellcheck disable=SC2086
"$PS_CXX" $PS_CXXFLAGS -std=c++17 -I"$PS_REPO" -I"$PS_INCLUDE" \
  "$PS_REPO/proofsmith_harness/harness.cpp" \
  "$PS_BUILD_DIR/liborderd_core.a" \
  $PS_LDFLAGS -pthread \
  -o "$PS_OUT/harness"
