#!/usr/bin/env bash
set -euo pipefail
export DEEPSEEK_API_KEY=""
original="$PWD"
clone_dir="$(mktemp -d "$HOME/psw/integration-clone.XXXXXX")"
git clone --quiet --no-hardlinks "$original" "$clone_dir"
cd "$clone_dir"
test ! -f .env
test -z "$(git status --porcelain)"
export PYTHONPATH="$PWD"
python - "$original" <<'PY'
import hashlib, json, subprocess, sys
from pathlib import Path
from proofsmith import config
from proofsmith.eval.protocol import validate_protocol
from proofsmith.gate import check_receipt
protocol = json.loads((config.REPO / 'docs/protocol.json').read_text())
validate_protocol(protocol)
manifests = list((config.RESULTS / 'tool-demo').rglob('manifest.json'))
manifests += list((config.RESULTS / 'integration/byteask-complete').rglob('manifest.json'))
manifests += list((config.RESULTS / 'integration/ci-smoke').rglob('manifest.json'))
for path in manifests:
    check_receipt(path.parent)
summary = json.loads((config.RESULTS / 'integration/byteask-complete/summary.json').read_text())
assert summary['exit_code'] == summary['headless_exit_code'] == 0
wheel = config.REPO / 'artifacts/proofsmith-0.2.0-py3-none-any.whl'
wheel_receipt = json.loads((config.RESULTS / 'integration-wheel-check.json').read_text())
assert hashlib.sha256(wheel.read_bytes()).hexdigest() == wheel_receipt['wheel_sha256']
subprocess.run(['bash', 'scripts/ci_gate.sh', str(config.REPO / 'fresh-ci-evidence')], check=True)
subprocess.run([sys.executable, 'scripts/check_byteask_transport.py', str(Path(sys.argv[1]) / '.tools/byteask/byteask-engine'),
                str(config.REPO / 'fresh-byteask-evidence')], check=True, stdout=subprocess.DEVNULL)
fresh = json.loads((config.REPO / 'fresh-byteask-evidence/summary.json').read_text())
assert fresh['exit_code'] == fresh['headless_exit_code'] == 0
receipt = {'schema': 'proofsmith.integration-clean-clone/1', 'source_commit': subprocess.check_output(['git', 'rev-parse', 'HEAD'], text=True).strip(),
           'clone_path': str(config.REPO), 'clean_before_execution': True, 'env_file_absent': True,
           'model_key_unset': True, 'protocol_id': protocol['id'], 'protocol_valid': True,
           'evidence_packages_checked': len(manifests), 'wheel_matches_tested_identity': True,
           'fresh_ci_fixed_status': 'VERIFIED', 'fresh_ci_unfixed_status': 'REJECTED',
           'fresh_actual_byteask_mcp_exit_code': fresh['exit_code'], 'fresh_actual_byteask_headless_exit_code': fresh['headless_exit_code'],
           'model_calls': 0, 'dependency_context': 'existing WSL Python environment, C++ toolchain and installed ByteAsk binary; scripted localhost provider; no upstream mirrors needed'}
(Path(sys.argv[1]) / 'results/integration-reproduction.json').write_text(json.dumps(receipt, indent=2) + '\n')
print(json.dumps(receipt))
PY
