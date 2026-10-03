#!/usr/bin/env bash
set -euo pipefail
cd "${HOME}/proofsmith"
source "${HOME}/.venvs/proofsmith/bin/activate"
python - <<'PY'
import shutil
from proofsmith import config
dest = config.REPO / 'scratch/budget-repair'
dest.mkdir(parents=True, exist_ok=True)
for name in ('proofsmith', 'config', 'tests', 'cases'):
    shutil.copytree(config.REPO / name, dest / name, dirs_exist_ok=True,
                    ignore=shutil.ignore_patterns('__pycache__', '*.pyc'))
shutil.copy2(config.REPO / 'pyproject.toml', dest / 'pyproject.toml')
print(dest)
PY
