#!/usr/bin/env bash
set -euo pipefail

repo="$PS_REPO"
cxx_path="$(command -v "$PS_CXX")"
out="$PS_OUT/harness"

mkdir -p "$PS_OUT"

cat > "$out" <<EOF
#!/usr/bin/env bash
set -euo pipefail

repo="$repo"
cxx="$cxx_path"
work="\$(mktemp -d)"
trap 'rm -rf "\$work"' EXIT

"\$cxx" -std=c++11 -I"\$repo/single_include" "\$repo/proofsmith_harness/repro.cpp" -o "\$work/repro"
"\$work/repro"
EOF

chmod +x "$out"
