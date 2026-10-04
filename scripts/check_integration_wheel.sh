#!/usr/bin/env bash
set -euo pipefail
export DEEPSEEK_API_KEY=""
root="$PWD"
install_dir="$(mktemp -d "$HOME/psw/integration-wheel.XXXXXX")"
python -m pip install --no-deps --no-index --target "$install_dir" artifacts/proofsmith-0.2.0-py3-none-any.whl
cd "$install_dir"
PYTHONPATH="$install_dir" PROOFSMITH_RESULTS_DIR="$install_dir/results" python - "$root" <<'PY'
import asyncio, hashlib, json, subprocess, sys
from pathlib import Path
import proofsmith
from proofsmith.datasets.schema import BuildRecipe
from proofsmith.gate import seal, check_patch, check_receipt, _copy_source
from proofsmith.mcp_server import create_server
root = Path(sys.argv[1])
installed = Path(proofsmith.__file__).resolve().parent
assert installed.is_relative_to(Path.cwd()), installed
out = Path.cwd() / 'test-evidence'
out.mkdir()
repo = root / 'examples/ci-smoke/original'
recipe = BuildRecipe(system='cmake')
qualified = seal(repo, root / 'examples/ci-smoke/harness', recipe, 'assertion', out / 'qualification')
assert qualified['status'] == 'VERIFIED', qualified
_copy_source(repo, out / 'candidate')
(out / 'candidate/calculation.cpp').write_text('int total(int a, int b) { return a + b; }\n')
receipt = check_patch(out / 'qualification/bundle', repo, out / 'candidate', recipe, out / 'gate', qualified['bundle_id'])
assert receipt['status'] == 'VERIFIED', receipt
assert (out / 'gate/index.html').is_file()
integrity = check_receipt(out / 'gate')
tools = {t.name for t in asyncio.run(create_server().list_tools())}
assert tools == {'seal_check', 'verify', 'check_patch', 'evidence_check'}, tools
subprocess.run([sys.executable, '-m', 'proofsmith.cli', 'evidence-check', str(out / 'gate')], check=True, stdout=subprocess.DEVNULL)
wheel = root / 'artifacts/proofsmith-0.2.0-py3-none-any.whl'
result = {'schema': 'proofsmith.wheel-check/1', 'installed_package_path': str(installed),
          'wheel_sha256': hashlib.sha256(wheel.read_bytes()).hexdigest(), 'external_to_checkout': True,
          'packaged_runtime_and_templates_work': True, 'offline_tools': sorted(tools),
          'gate_status': receipt['status'], 'baseline_target_failures': receipt['baseline']['target_failures'],
          'candidate_failures': receipt['candidate']['fails'], 'integrity': integrity, 'model_calls': 0,
          'dependency_context': 'wheel installed with no dependencies; existing WSL Python environment and C++ toolchain'}
(root / 'results/integration-wheel-check.json').write_text(json.dumps(result, indent=2) + '\n')
print(json.dumps(result))
PY
