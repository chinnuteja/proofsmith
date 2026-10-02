#!/usr/bin/env bash
set -euo pipefail

mkdir -p "$PS_OUT"

"$PS_CXX" $PS_CXXFLAGS \
  -std=c++17 \
  -I"$PS_REPO" \
  -I"$PS_INCLUDE" \
  proofsmith_harness/harness.cpp \
  "$PS_BUILD_DIR/liborderd_core.a" \
  -pthread \
  $PS_LDFLAGS \
  -o "$PS_OUT/harness"
