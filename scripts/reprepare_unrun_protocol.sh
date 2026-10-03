#!/usr/bin/env bash
set -euo pipefail
cd "${HOME}/proofsmith"
source "${HOME}/.venvs/proofsmith/bin/activate"
python - <<'PY'
import json
from proofsmith import config
from proofsmith.eval.protocol import PROTOCOL_PATH, fingerprint
from proofsmith.eval.runner import read_rows, result_root
protocol = json.loads(PROTOCOL_PATH.read_text())
if read_rows(protocol) or list(result_root(protocol).rglob('*.attempt.json')):
    raise SystemExit('Refusing to change a protocol after an observation or attempted generation')
history = config.REPO / 'docs/protocol-history'
history.mkdir(exist_ok=True)
(history / (fingerprint(protocol) + '.json')).write_bytes(PROTOCOL_PATH.read_bytes())
PROTOCOL_PATH.unlink()
print('Unrun preparation archived; no experimental observation was discarded.')
PY
bash scripts/prepare_evaluation.sh
