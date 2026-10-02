#!/usr/bin/env bash
set -euo pipefail

mkdir -p "$PS_OUT"

"$PS_CXX" -std=c++17 $PS_CXXFLAGS \
  -I"$PS_REPO" \
  "$PS_REPO/proofsmith_harness/deadlock_repro.cpp" \
  "$PS_REPO/order_book.cpp" \
  -pthread $PS_LDFLAGS \
  -o "$PS_OUT/harness"
