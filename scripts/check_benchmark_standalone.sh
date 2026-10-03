#!/usr/bin/env bash
set -euo pipefail
cd "${HOME}/proofsmith/benchmark"
source "${HOME}/.venvs/proofsmith/bin/activate"
export DEEPSEEK_API_KEY=""
export PYTHONPATH="$PWD"
python -m proofsmith.cli evaluate --bundle results/eval/B/spdlog-1570/b1 \
  --instance data/trackB/instances/spdlog-1570.json \
  --hidden data/trackB/hidden/spdlog-1570.json --out standalone-verdict.json
python - <<'PY'
import json
from pathlib import Path
from proofsmith.config import REPO
value = json.loads(Path('standalone-verdict.json').read_text())
assert REPO == Path.cwd()
assert value['build_ok_buggy'] and value['build_ok_fixed']
assert value['buggy_fails'] == 20 and value['fixed_fails'] == 0
assert value['f2p'] and not value['alignment']['strict']
print('standalone benchmark: PASS (actual frozen B1 verifier, no model key)')
PY
