#!/usr/bin/env bash
set -euo pipefail

mkdir -p "$PS_OUT"

"$PS_CXX" ${PS_CXXFLAGS:-} -std=c++17 -I"$PS_REPO" -I"$PS_INCLUDE" \
  -c proofsmith_harness/harness.cpp -o "$PS_OUT/harness.o"

"$PS_CXX" ${PS_CXXFLAGS:-} "$PS_OUT/harness.o" "$PS_BUILD_DIR/libcore.a" \
  ${PS_LDFLAGS:-} -o "$PS_OUT/harness"
