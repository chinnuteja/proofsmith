#!/usr/bin/env bash
set -euo pipefail
"$PS_CXX" -std=c++17 $PS_CXXFLAGS -I"$PS_REPO/include" -I"$PS_INCLUDE" \
  "$PS_REPO/proofsmith_harness/harness.cpp" $PS_LDFLAGS -o "$PS_OUT/harness"
