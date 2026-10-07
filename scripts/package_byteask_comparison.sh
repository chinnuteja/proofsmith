#!/usr/bin/env bash
set -euo pipefail
export DEEPSEEK_API_KEY=""
python - <<'PY'
import hashlib, json, sys, tomllib, zipfile
from pathlib import Path
sys.path.insert(0, str(Path.cwd() / 'scripts'))
from byteask_comparison import validate, digest
from proofsmith.gate import check_receipt
root = Path.cwd()
experiment = root / 'experiments/byteask-comparison/v1'
protocol = validate(experiment)
summary = json.loads((experiment / 'offline-results.json').read_text())
assert digest(experiment / 'protocol.json') == summary['protocol_sha256']
assert summary['model_calls'] == 0 and len(summary['controls']) == 15
assert summary['counts']['incorrect_controls_not_approved'] == 10
assert summary['counts']['correct_controls_approved'] == 5
for receipt in (experiment / 'evidence').rglob('receipt.json'):
    check_receipt(receipt.parent)
wheel = root / 'artifacts/proofsmith-0.2.0-py3-none-any.whl'
assert digest(wheel) == 'ab3806d422cc629282904823eac8078990b6ace94817b95866a352abfa6fe847'
paths = {p for p in experiment.rglob('*') if p.is_file()}
live = root / 'experiments/byteask-comparison/live-v1'
scored = root / 'experiments/byteask-comparison/live-v1-score'
live_metrics = None
if (scored / 'results.json').is_file():
    live_result = json.loads((scored / 'results.json').read_text())
    assert live_result['protocol_sha256'] == summary['protocol_sha256']
    live_metrics = live_result['metrics']
    assert live_metrics['observations'] == len(json.loads((live / 'observations.json').read_text()))
    for receipt in scored.rglob('receipt.json'):
        check_receipt(receipt.parent)
    paths.update(p for tree in (live, scored) for p in tree.rglob('*') if p.is_file())
paths.add(wheel)
paths.update(root / relative for relative in protocol['implementation_hashes'])
old = json.loads((root / 'docs/protocol.json').read_text())
paths.update(root / relative for relative in old['files'])
paths.update(p for p in (root / 'proofsmith').rglob('*') if p.is_file() and '__pycache__' not in p.parts and p.suffix != '.pyc')
paths.update(root / relative for relative in (
    'docs/byteask-comparison.md', 'docs/byteask-live-comparison.md', 'docs/byteask-integration.md', 'docs/verification-tool.md', 'docs/byteask-review.md',
    'docs/phase-logs/byteask-comparison-2026-10-07.md',
    'scripts/byteask_comparison.sh', 'scripts/comparison_preflight.sh', 'scripts/check_byteask_comparison.sh',
    'scripts/finalize_byteask_comparison.sh', 'scripts/package_byteask_comparison.sh',
    'scripts/ws.ps1', 'scripts/byteask_local.sh', 'scripts/install_byteask_local.sh',
    'scripts/configure_byteask_local.sh', 'scripts/check_byteask_comparison_browser.sh',
    'scripts/byteask_comparison_live.py', 'scripts/byteask_comparison_live.sh',
    'scripts/byteask_account_status.sh', 'scripts/check_byteask_live_policy.sh',
    'scripts/check_byteask_comparison_package.sh',
    'scripts/report_byteask_comparison.py', 'scripts/report_byteask_live.sh',
    'scripts/rescore_byteask_comparison.py', 'scripts/rescore_byteask_comparison.sh',
    'scripts/check_byteask_live_browser.sh', 'results/byteask-transfer-authorization.json',
    'tests/phase9/test_byteask_comparison.py', 'tests/phase9/test_byteask_live_policy.py',
    'results/byteask-comparison-browser.json'))
if (root / 'results/byteask-live-browser.json').is_file():
    paths.add(root / 'results/byteask-live-browser.json')
private_config = root / '.tools/byteask-home/config.toml'
managed_token = None
if private_config.is_file():
    managed = tomllib.loads(private_config.read_text())
    managed_token = managed.get('model_providers', {}).get('byteask', {}).get('experimental_bearer_token')
if managed_token:
    for path in paths:
        if managed_token.encode() in path.read_bytes():
            raise ValueError('managed credential found in export; refuse packaging')
archive = root / 'artifacts/proofsmith-byteask-evaluation-kit.zip'
observations = live_metrics['observations'] if live_metrics else 0
claim = live_metrics['claim'] if live_metrics else 'No real model comparison has been scored.'
with zipfile.ZipFile(archive, 'w', zipfile.ZIP_DEFLATED) as package:
    package.writestr('START-HERE.md', '# Proofsmith evaluation kit\n\n'
                    f'Real ByteAsk observations: {observations}/5. {claim}. Additional purchases: $0.\n\n'
                    'Read docs/byteask-review.md for the product overview. '
                    'Open experiments/byteask-comparison/live-v1-score/index.html for real results, '
                    'patches, recorded tool output and gate receipts. Read docs/byteask-live-comparison.md. '
                    'The separate v1/index.html shows fifteen authored offline controls; those are excluded '
                    'from model scores. Five synthetic cases do not establish broad superiority.\n\n'
                    'Install on Linux/WSL with Python 3.12+, clang++, CMake and bubblewrap. In a virtual '
                    'environment, run `pip install "./artifacts/proofsmith-0.2.0-py3-none-any.whl[mcp]"`. '
                    'Then run `bash scripts/rescore_byteask_comparison.sh --out /tmp/proofsmith-real-recheck` '
                    'to compile and evaluate the retained real patches afresh, without a model or account. '
                    'Use a new output path. Read docs/verification-tool.md and docs/byteask-integration.md '
                    'to use the CLI, MCP or CI gate on your own original/candidate pair.\n\n'
                    'Original collection records retain their original absolute paths. The offline '
                    'rescorer rebases only a temporary copy and preserves transcript hashes. Recorded '
                    'timings are machine-dependent. Hashes bind bytes, not authorship. No credentials '
                    'or ByteAsk binary are included. This archive has not been published or sent.\n')
    for path in sorted(paths):
        if path.is_symlink() or '.tools' in path.parts or path.name == '.env':
            raise ValueError('unexpected private file or symlink')
        package.write(path, path.relative_to(root).as_posix())
with zipfile.ZipFile(archive) as package:
    assert package.testzip() is None
    entries = len(package.namelist())
record = {'schema': 'proofsmith.byteask-evaluation-package/1', 'path': str(archive.relative_to(root)),
          'sha256': digest(archive), 'bytes': archive.stat().st_size, 'entries': entries,
          'protocol_sha256': summary['protocol_sha256'], 'model_observations': observations,
          'offline_controls': 15, 'published': False, 'zip_integrity_ok': True,
          'byteask_binary_included': False, 'winning_claim': bool(live_metrics and live_metrics['positive_pilot_signal']),
          'managed_credential_scan_passed': bool(managed_token),
          'live_metrics': live_metrics}
(root / 'results/byteask-comparison-package.json').write_text(json.dumps(record, indent=2) + '\n')
print(json.dumps(record, indent=2))
PY
