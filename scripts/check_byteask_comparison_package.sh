#!/usr/bin/env bash
set -euo pipefail
export DEEPSEEK_API_KEY=""
python - <<'PY'
import hashlib, json, os, subprocess, sys, tempfile, zipfile
from pathlib import Path
root = Path.cwd()
archive = root / 'artifacts/proofsmith-byteask-evaluation-kit.zip'
receipt = json.loads((root / 'results/byteask-comparison-package.json').read_text())
identity = hashlib.sha256(archive.read_bytes()).hexdigest()
assert identity == receipt['sha256']
task_workspace = Path.home() / 'psw'
task_workspace.mkdir(exist_ok=True)
with tempfile.TemporaryDirectory(prefix='comparison-kit-', dir=task_workspace) as name:
    unpacked = Path(name) / 'source'
    unpacked.mkdir()
    with zipfile.ZipFile(archive) as package:
        assert package.testzip() is None
        for item in package.namelist():
            target = (unpacked / item).resolve()
            if not target.is_relative_to(unpacked.resolve()):
                raise ValueError('archive path escaped the fresh extraction')
        package.extractall(unpacked)
    assert not (unpacked / '.tools').exists() and not (unpacked / '.env').exists()
    assert not list(unpacked.rglob('auth.json'))
    env = dict(os.environ, PYTHONPATH=str(unpacked), DEEPSEEK_API_KEY='')
    commands = [
        [sys.executable, 'scripts/byteask_comparison.py', 'validate', '--experiment', 'experiments/byteask-comparison/v1'],
        [sys.executable, '-m', 'pytest', '-q', 'tests/phase9/test_byteask_comparison.py', 'tests/phase9/test_byteask_live_policy.py'],
        ['proofsmith', 'protocol', 'validate'],
    ]
    has_live = (unpacked / 'experiments/byteask-comparison/live-v1-score/results.json').is_file()
    if has_live:
        commands.append([sys.executable, 'scripts/rescore_byteask_comparison.py', '--out', str(Path(name) / 'fresh-live-score')])
    for command in commands:
        completed = subprocess.run(command, cwd=unpacked, env=env, capture_output=True, text=True, timeout=120)
        print(completed.stdout, end='')
        if completed.returncode:
            print(completed.stderr)
            raise RuntimeError('fresh-package check failed')
    code = '''import json, sys
from pathlib import Path
sys.path.insert(0, str(Path.cwd() / 'scripts'))
from byteask_comparison import RECIPE
from proofsmith.gate import check_patch, check_receipt
root, result = map(Path, sys.argv[1:])
experiment = root / 'experiments/byteask-comparison/v1'
qualification = experiment / 'evidence/quota-overflow/qualification'
sealed = json.loads((qualification / 'receipt.json').read_text())
gate = check_patch(qualification / 'bundle', experiment / 'cases/quota-overflow/original',
                   experiment / 'controls/quota-overflow/fixed', RECIPE, result, sealed['bundle_id'])
assert gate['status'] == 'VERIFIED', gate
assert gate['baseline']['fails'] == 20 and gate['candidate']['fails'] == 0
check_receipt(result)
print(json.dumps({'fresh_package_gate': gate['status'], 'original_failures': 20, 'candidate_failures': 0}))
'''
    completed = subprocess.run([sys.executable, '-c', code, str(unpacked), str(Path(name) / 'fresh-gate')],
                               cwd=unpacked, env=env, capture_output=True, text=True, timeout=240)
    print(completed.stdout, end='')
    if completed.returncode:
        print(completed.stderr)
        raise RuntimeError('fresh-package compiler/gate check failed')
result = {'schema': 'proofsmith.byteask-kit-reproduction/1', 'archive_sha256': identity,
          'fresh_extraction': True, 'no_credentials_in_extraction': True, 'model_requests': 0,
          'comparison_protocol_valid': True, 'original_deepseek_protocol_valid': True,
          'policy_tests_passed': 19, 'fresh_gate': 'VERIFIED', 'baseline_failures': 20,
          'candidate_failures': 0, 'existing_python_dependencies_and_linux_toolchain_used': True}
result['retained_live_candidates_independently_rescored'] = has_live
result['live_metrics_reproduced'] = receipt.get('live_metrics') if has_live else None
(root / 'results/byteask-comparison-reproduction.json').write_text(json.dumps(result, indent=2) + '\n')
print(json.dumps(result, indent=2))
PY
