#!/usr/bin/env bash
set -euo pipefail
cd "${HOME}/proofsmith"
source "${HOME}/.venvs/proofsmith/bin/activate"
export DEEPSEEK_API_KEY=""
python - <<'PY'
from proofsmith import config
from proofsmith.upstream_demo import run_demo
print(run_demo(config.RESULTS / 'tool-demo/catch2'))
PY
