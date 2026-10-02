#!/usr/bin/env bash
set -euo pipefail

CXX="${PS_CXX:-clang++}"
CXXFLAGS="${PS_CXXFLAGS:-}"
LDFLAGS="${PS_LDFLAGS:-}"

mkdir -p "$PS_OUT"

# Compile the real implementation together with the harness.  The variant's
# sanitizer flags (e.g. -fsanitize=thread) come from PS_CXXFLAGS/PS_LDFLAGS.
"$CXX" -std=c++17 $CXXFLAGS \
  -I"$PS_REPO" -I"$PS_INCLUDE" \
  "$PS_REPO/metrics.cpp" \
  "$PS_REPO/proofsmith_harness/harness.cpp" \
  -pthread $LDFLAGS -o "$PS_OUT/harness.bin"

# A wrapper keeps a ThreadSanitizer report from being ignored: the first race
# report must make the harness exit non-zero.
cat > "$PS_OUT/harness" <<'EOF'
#!/usr/bin/env bash
export TSAN_OPTIONS="halt_on_error=1:exitcode=99${TSAN_OPTIONS:+:$TSAN_OPTIONS}"
exec "$(dirname "$0")/harness.bin" "$@"
EOF
chmod +x "$PS_OUT/harness"
