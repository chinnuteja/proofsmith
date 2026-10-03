#!/usr/bin/env bash
set -euo pipefail
cd "${HOME}/proofsmith"
source "${HOME}/.venvs/proofsmith/bin/activate"
proofsmith protocol freeze
proofsmith metrics
python - <<'PY'
import json
from proofsmith.eval.protocol import PROTOCOL_PATH
from proofsmith.eval.preflight import estimate
print(json.dumps(estimate(json.loads(PROTOCOL_PATH.read_text())), indent=2))
PY
proofsmith report readme
proofsmith report build
