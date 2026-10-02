#!/usr/bin/env bash
set -euo pipefail

"${PS_CXX}" ${PS_CXXFLAGS} -std=c++17 -I"${PS_REPO}" \
  "${PS_REPO}/proofsmith_harness/harness.cpp" \
  "${PS_REPO}/price_cache.cpp" \
  -o "${PS_OUT}/harness" ${PS_LDFLAGS}
