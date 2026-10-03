#!/usr/bin/env bash
set -euo pipefail
export DEBIAN_FRONTEND=noninteractive
apt-get update -qq
apt-get install -y -qq universal-ctags gh iproute2 curl jq bubblewrap
/home/*/.venvs/proofsmith/bin/python -m playwright install-deps chromium || true
echo "setup_root: OK"
