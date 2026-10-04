#!/usr/bin/env bash
set -euo pipefail
cd "${HOME}/proofsmith"
source "${HOME}/.venvs/proofsmith/bin/activate"
export DEEPSEEK_API_KEY=""
export PROOFSMITH_RECORD_TOOL_DEMO=1
bash scripts/check_offline.sh
