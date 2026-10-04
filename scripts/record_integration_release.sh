#!/usr/bin/env bash
set -euo pipefail
export DEEPSEEK_API_KEY=""
python - <<'PY'
import json, shutil
from pathlib import Path
from proofsmith import config
from proofsmith.gate import check_receipt
source = config.WORK / 'integration-ci-20261004'
destination = config.RESULTS / 'integration/ci-smoke'
if destination.exists():
    raise RuntimeError('CI evidence already recorded; retain it')
for name in ('qualification', 'fixed', 'unfixed'):
    check_receipt(source / name)
shutil.copytree(source, destination)
summary = {'schema': 'proofsmith.ci-check/1', 'mode': 'local execution of workflow script; real C++ supplied fixture',
           'github_execution_tested': False, 'model_calls': 0,
           'fixed_status': json.loads((destination / 'fixed/receipt.json').read_text())['status'],
           'unfixed_status': json.loads((destination / 'unfixed/receipt.json').read_text())['status']}
(destination / 'summary.json').write_text(json.dumps(summary, indent=2) + '\n')
print(json.dumps(summary))
PY
