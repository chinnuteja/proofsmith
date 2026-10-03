#!/usr/bin/env bash
set -euo pipefail

"${PS_CXX}" ${PS_CXXFLAGS} ${PS_LDFLAGS} -std=c++17 -O2 -I"${PS_REPO}" \
  "${PS_REPO}/proofsmith_harness/harness.cpp" \
  "${PS_REPO}/match.cpp" \
  -o "${PS_OUT}/harness"
