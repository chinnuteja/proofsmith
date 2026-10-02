#!/usr/bin/env bash
set -euo pipefail
mkdir -p "$PS_BUILD_DIR"
cat > "$PS_BUILD_DIR/smoke.cpp" << 'EOF'
#include "concurrentqueue.h"

int main() {
  moodycamel::ConcurrentQueue<int> queue;
  int value = 0;
  queue.enqueue(1);
  if (!queue.try_dequeue(value)) {
    return 1;
  }
  return value == 1 ? 0 : 1;
}
EOF
# Word-splitting is intentional: PS_CXXFLAGS is a flag string.
# shellcheck disable=SC2086
"$PS_CXX" $PS_CXXFLAGS -std=c++17 -I"$PS_REPO" "$PS_BUILD_DIR/smoke.cpp" $PS_LDFLAGS -pthread -o "$PS_BUILD_DIR/smoke"
python3 - "$PS_BUILD_DIR" "$PS_REPO" "$PS_CXX" "$PS_CXXFLAGS" "$PS_LDFLAGS" << 'PY'
import json
import shlex
import sys
from pathlib import Path

build, repo, cxx, cxxflags, ldflags = sys.argv[1:]
command = [cxx, *shlex.split(cxxflags), "-std=c++17", "-I", repo, str(Path(build) / "smoke.cpp"), *shlex.split(ldflags), "-pthread", "-o", str(Path(build) / "smoke")]
payload = [{"directory": repo, "file": str(Path(build) / "smoke.cpp"), "command": " ".join(command)}]
Path(build, "compile_commands.json").write_text(json.dumps(payload) + "\n", encoding="utf-8")
PY
