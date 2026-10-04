#!/usr/bin/env bash
set -euo pipefail
export DEEPSEEK_API_KEY=""
exec python scripts/check_byteask_transport.py .tools/byteask/byteask-engine "${1:-results/integration/byteask-complete}"
