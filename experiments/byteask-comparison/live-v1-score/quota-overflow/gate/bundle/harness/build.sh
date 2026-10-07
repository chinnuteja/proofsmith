#!/usr/bin/env bash
set -euo pipefail
"$PS_CXX" $PS_CXXFLAGS -I"$PS_INCLUDE" -I"$PS_REPO" \
  "$PS_REPO/proofsmith_harness/harness.cpp" "$PS_BUILD_DIR/libsubject.a" \
  $PS_LDFLAGS -o "$PS_OUT/harness"
