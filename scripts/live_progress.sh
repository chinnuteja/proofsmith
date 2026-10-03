#!/usr/bin/env bash
set -euo pipefail
cd "${HOME}/proofsmith"
source "${HOME}/.venvs/proofsmith/bin/activate"
python - <<'PY'
import json
from proofsmith import config
from proofsmith.ledger import Ledger, LEDGER_PATH
print(f'recorded spend: ${Ledger(LEDGER_PATH).spent_usd():.6f}')
if LEDGER_PATH.exists():
    rows = [json.loads(line) for line in LEDGER_PATH.read_text().splitlines() if line.strip()]
    for row in rows[-3:]:
        print(row['ts'], row['run_id'], row['usage']['prompt_tokens'], row['usage']['completion_tokens'])
for name in ('rounding-ticks', 'vague-perf'):
    for system in ('b0', 'b1'):
        path = config.RESULTS / 'dryrun' / name / f'{system}.json'
        print('dryrun', name, system, 'recorded' if path.exists() else 'pending')
protocol_path = config.REPO / 'docs/protocol.json'
if protocol_path.exists():
    from proofsmith.eval.runner import read_rows
    protocol = json.loads(protocol_path.read_text())
    rows = read_rows(protocol)
    print('protocol observations:', len(rows))
    for row in rows:
        print(row['track'], row['instance_id'], row['system'], row['bundle_status'], row['f2p'])
PY
