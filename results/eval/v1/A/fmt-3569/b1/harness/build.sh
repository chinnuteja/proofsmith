#!/usr/bin/env bash
set -euo pipefail

: "${PS_REPO:?PS_REPO is required}"
: "${PS_OUT:?PS_OUT is required}"
: "${PS_CXX:?PS_CXX is required}"

mkdir -p "$PS_OUT"

# shellcheck disable=SC2086
"$PS_CXX" -std=c++17 \
  -I"$PS_REPO/include" \
  "$PS_REPO/proofsmith_harness/repro.cpp" \
  $PS_CXXFLAGS \
  -o "$PS_OUT/harness" \
  $PS_LDFLAGS
