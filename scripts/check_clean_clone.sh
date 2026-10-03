#!/usr/bin/env bash
set -euo pipefail
source "${HOME}/.venvs/proofsmith/bin/activate"
source_root="${HOME}/proofsmith"
clone="$(mktemp -d "${HOME}/psw/clean-clone.XXXXXX")"
git clone --quiet --no-hardlinks "$source_root" "$clone"
cd "$clone"
test ! -f .env
test -z "$(git status --porcelain)"
export PYTHONPATH="$PWD"
export DEEPSEEK_API_KEY=""
python -m proofsmith.cli protocol validate
set +e
bash scripts/reproduce.sh > reproduce.log 2>&1
reproduced=$?
set -e
python - "$source_root" "$clone" "$reproduced" <<'PY'
import json
import shutil
import subprocess
import sys
from pathlib import Path
from proofsmith.eval.runner import atomic_json
root, clone, code = Path(sys.argv[1]), Path(sys.argv[2]), int(sys.argv[3])
summary_path = clone / 'results/replay_summary.json'
summary = json.loads(summary_path.read_text()) if summary_path.exists() else {}
receipt = {'schema': 'proofsmith.clean-clone/1', 'source_commit': subprocess.check_output(['git', 'rev-parse', 'HEAD'], text=True).strip(),
    'clone_path': str(clone), 'clean_before_execution': True, 'env_file_absent': True,
    'model_key_unset': True, 'exit_code': code, 'bundles_checked': len(summary.get('records', [])),
    'all_verdicts_match': summary.get('matches', False), 'dependency_context': 'existing WSL toolchain and cached pinned upstream mirrors'}
atomic_json(root / 'results/reproduction_receipt.json', receipt)
if code == 0:
    old = root / 'results/replay_summary.json'
    if old.exists():
        archived = root / 'results/history/replay-before-reference-migration.json'
        if not archived.exists():
            shutil.copy2(old, archived)
    shutil.copy2(summary_path, old)
    shutil.copytree(clone / 'results/replay', root / 'results/replay', dirs_exist_ok=True)
print(json.dumps(receipt, indent=2))
if code:
    print('Reproduction failed; inspect ' + str(clone / 'reproduce.log'))
PY
exit "$reproduced"
