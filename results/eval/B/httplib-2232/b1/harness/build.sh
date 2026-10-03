#!/usr/bin/env bash
set -euo pipefail

"${PS_CXX}" \
  -std=c++11 \
  -DCPPHTTPLIB_USE_NON_BLOCKING_GETADDRINFO \
  -I"${PS_REPO}" \
  -I"${PS_INCLUDE}" \
  "${PS_REPO}/proofsmith_harness/harness.cpp" \
  ${PS_CXXFLAGS} \
  ${PS_LDFLAGS} \
  -pthread \
  -o "${PS_OUT}/harness"
