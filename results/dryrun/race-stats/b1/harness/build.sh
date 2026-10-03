#!/usr/bin/env bash
set -euo pipefail

: "${PS_CXX:?PS_CXX is required}"
: "${PS_REPO:?PS_REPO is required}"
: "${PS_BUILD_DIR:?PS_BUILD_DIR is required}"
: "${PS_INCLUDE:?PS_INCLUDE is required}"
: "${PS_OUT:?PS_OUT is required}"

mkdir -p "${PS_OUT}"

# shellcheck disable=SC2086
"${PS_CXX}" \
  -std=c++17 \
  -O1 -g \
  ${PS_CXXFLAGS} \
  -I"${PS_REPO}" \
  -I"${PS_INCLUDE}" \
  "${PS_REPO}/proofsmith_harness/harness.cc" \
  "${PS_BUILD_DIR}/libcore.a" \
  -pthread \
  ${PS_LDFLAGS} \
  -o "${PS_OUT}/harness"
