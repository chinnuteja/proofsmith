#!/usr/bin/env bash
set -euo pipefail
cd "${HOME}/proofsmith"
source "${HOME}/.venvs/proofsmith/bin/activate"
python - <<'PY'
import difflib
from proofsmith import config
paths = ('proofsmith/agent/loop.py', 'proofsmith/pipeline.py',
         'tests/phase3/test_pipeline_fake.py', 'tests/phase5/test_systems_fake.py',
         'tests/phase6/test_token_reservation.py')
parts = []
for rel in paths:
    original = config.REPO / rel
    candidate = config.REPO / 'scratch/budget-repair' / rel
    before = original.read_text().splitlines(keepends=True) if original.exists() else []
    after = candidate.read_text().splitlines(keepends=True)
    parts.extend(difflib.unified_diff(before, after, fromfile='a/' + rel if original.exists() else '/dev/null', tofile='b/' + rel))
dest = config.REPO / 'docs/repairs'
dest.mkdir(exist_ok=True)
(dest / 'token-budget.patch').write_text(''.join(parts))
print(dest / 'token-budget.patch')
PY
