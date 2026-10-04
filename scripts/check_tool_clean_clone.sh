#!/usr/bin/env bash
set -euo pipefail
source "${HOME}/.venvs/proofsmith/bin/activate"
source_root="${HOME}/proofsmith"
clone_dir="$(mktemp -d "${HOME}/psw/tool-clone.XXXXXX")"
git clone --quiet --no-hardlinks "$source_root" "$clone_dir"
cd "$clone_dir"
test ! -f .env
test -z "$(git status --porcelain)"
export PYTHONPATH="$PWD"
export DEEPSEEK_API_KEY=""
python - "$source_root" <<'PY'
import json
import subprocess
import sys
from pathlib import Path
from proofsmith import config
from proofsmith.eval.protocol import validate_protocol
from proofsmith.gate import check_receipt
from proofsmith.upstream_demo import run_demo
root = Path(sys.argv[1])
protocol = json.loads((config.REPO / 'docs/protocol.json').read_text())
validate_protocol(protocol)
manifests = list((config.RESULTS / 'tool-demo').rglob('manifest.json'))
for path in manifests:
    check_receipt(path.parent)
result_dir = run_demo(config.RESULTS / 'tool-replay-catch2')
result = json.loads((result_dir / 'summary.json').read_text())
receipt = {'schema': 'proofsmith.tool-clean-clone/1',
           'source_commit': subprocess.check_output(['git','rev-parse','HEAD'], text=True).strip(),
           'clone_path': str(config.REPO), 'clean_before_execution': True, 'env_file_absent': True,
           'model_key_unset': True, 'protocol_valid': True, 'protocol_id': protocol['id'],
           'evidence_packages_checked': len(manifests), 'upstream_status': result['status'],
           'upstream_original_target_failures': result['baseline_target_failures'],
           'upstream_fixed_target_failures': result['candidate_target_failures'], 'n': result['n'],
           'model_calls': 0, 'dependency_context': 'existing WSL toolchain and cached pinned upstream source mirrors'}
(root / 'results/tool-reproduction.json').write_text(json.dumps(receipt, indent=2) + '\n')
print(json.dumps(receipt))
PY
