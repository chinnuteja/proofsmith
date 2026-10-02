#!/usr/bin/env bash
# Compile a consumer of a header-only C++ project and record compile_commands.json.
# CMake configure still runs. These trees have no compiled target, so CMake writes
# no compile_commands.json and the build cache would otherwise treat them as failed.
set -euo pipefail
mkdir -p "${PS_BUILD_DIR}"
smoke="${PS_BUILD_DIR}/smoke.cpp"
inc=()
if [[ -f "${PS_REPO}/include/nlohmann/json.hpp" ]]; then
  inc+=(-I "${PS_REPO}/include")
  cat > "${smoke}" << 'EOF'
#include <nlohmann/json.hpp>
int main() {
  nlohmann::json value = 1;
  return value.is_number() ? 0 : 1;
}
EOF
elif [[ -f "${PS_REPO}/src/json.hpp" ]]; then
  inc+=(-I "${PS_REPO}/src")
  cat > "${smoke}" << 'EOF'
#include "json.hpp"
int main() {
  nlohmann::json value = 1;
  return value.is_number() ? 0 : 1;
}
EOF
elif [[ -f "${PS_REPO}/include/catch.hpp" ]]; then
  inc+=(-I "${PS_REPO}/include")
  cat > "${smoke}" << 'EOF'
#include <catch.hpp>
int main() { return 0; }
EOF
elif [[ -f "${PS_REPO}/single_include/catch2/catch.hpp" ]]; then
  inc+=(-I "${PS_REPO}/single_include")
  cat > "${smoke}" << 'EOF'
#include <catch2/catch.hpp>
int main() { return 0; }
EOF
else
  echo "no public header found" >&2
  exit 1
fi

if [[ -f "${PS_REPO}/CMakeLists.txt" ]]; then
  # Tests stay off. Header-only trees still configure; the consumer compile below
  # is what produces compile_commands.json.
  cmake -S "${PS_REPO}" -B "${PS_BUILD_DIR}/cmake" -G Ninja \
    -DCMAKE_CXX_COMPILER="${PS_CXX}" \
    -DCMAKE_BUILD_TYPE= \
    -DCMAKE_CXX_FLAGS="${PS_CXXFLAGS}" \
    -DCMAKE_EXE_LINKER_FLAGS="${PS_LDFLAGS}" \
    -DJSON_BuildTests=OFF \
    -DJSON_CI=OFF \
    -DJSON_Install=OFF \
    -DCATCH_BUILD_TESTING=OFF \
    -DCATCH_BUILD_EXAMPLES=OFF \
    -DCATCH_INSTALL_DOCS=OFF \
    -DBUILD_TESTING=OFF
  cmake --build "${PS_BUILD_DIR}/cmake" -j 4
fi

cmd=("${PS_CXX}")
# shellcheck disable=SC2086
cmd+=(${PS_CXXFLAGS})
cmd+=(-std=c++17)
cmd+=("${inc[@]}")
cmd+=("${smoke}" -o "${PS_BUILD_DIR}/smoke")
# shellcheck disable=SC2086
cmd+=(${PS_LDFLAGS})
"${cmd[@]}"

python3 - "${PS_BUILD_DIR}" "${smoke}" "${cmd[@]}" << 'PY'
import json
import sys
from pathlib import Path

build_dir = Path(sys.argv[1])
source = sys.argv[2]
command = sys.argv[3:]
payload = [
    {
        "directory": str(build_dir),
        "command": " ".join(command),
        "file": source,
        "output": str(build_dir / "smoke"),
    }
]
(build_dir / "compile_commands.json").write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
PY
