#!/usr/bin/env bash
set -euo pipefail

: "${PS_CXX:?PS_CXX is required}"
: "${PS_CXXFLAGS:?PS_CXXFLAGS is required}"
: "${PS_LDFLAGS:?PS_LDFLAGS is required}"
: "${PS_REPO:?PS_REPO is required}"
: "${PS_OUT:?PS_OUT is required}"

mkdir -p "$PS_OUT"

# -Wl,--wrap=getaddrinfo redirects httplib's getaddrinfo calls to
# __wrap_getaddrinfo so the test can simulate a slow DNS lookup
# deterministically, without touching the host resolver.
"$PS_CXX" -std=c++11 -pthread \
  -I"$PS_REPO" \
  $PS_CXXFLAGS \
  -Wl,--wrap=getaddrinfo \
  "$PS_REPO/proofsmith_harness/main.cpp" \
  -o "$PS_OUT/harness" \
  $PS_LDFLAGS
