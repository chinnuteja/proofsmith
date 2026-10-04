#!/usr/bin/env bash
set -euo pipefail
export DEEPSEEK_API_KEY=""
python - <<'PY'
import hashlib, json, zipfile
from pathlib import Path
from proofsmith import config
from proofsmith.gate import check_receipt
root = config.REPO
transport = config.RESULTS / 'integration/byteask-complete'
for name in ('evidence', 'headless/evidence'):
    check_receipt(transport / name)
archive = root / 'artifacts/proofsmith-integration-0.2.0.zip'
includes = [root / 'artifacts/proofsmith-0.2.0-py3-none-any.whl', root / 'README.md',
            root / 'docs/byteask-integration.md', root / 'docs/verification-tool.md',
            root / '.github/workflows/verification-tool.yml']
includes += [root / 'scripts' / name for name in ('ci_gate.sh', 'byteask_gate.sh', 'byteask_local.sh',
             'install_byteask_local.sh', 'configure_byteask_local.sh', 'check_byteask_transport.sh', 'check_byteask_transport.py')]
includes += [root / 'pyproject.toml']
includes += [p for p in (root / 'proofsmith').rglob('*') if p.is_file() and '__pycache__' not in p.parts and p.suffix != '.pyc']
includes += [p for p in (root / 'examples/ci-smoke').rglob('*') if p.is_file()]
includes += [p for p in transport.rglob('*') if p.is_file()]
includes += [p for p in (config.RESULTS / 'integration/ci-smoke').rglob('*') if p.is_file()]
includes += [root / 'results' / name for name in ('integration-wheel-check.json', 'integration-browser-check.json', 'byteask-installation.json', 'integration-reproduction.json')]
includes += [root / 'docs/phase-logs/integration-2026-10-04.md']
with zipfile.ZipFile(archive, 'w', zipfile.ZIP_DEFLATED) as package:
    for path in sorted(includes):
        package.write(path, path.relative_to(root).as_posix())
with zipfile.ZipFile(archive) as package:
    assert package.testzip() is None
    entries = len(package.namelist())
receipt = {'schema': 'proofsmith.integration-package/1', 'path': str(archive.relative_to(root)),
           'sha256': hashlib.sha256(archive.read_bytes()).hexdigest(), 'bytes': archive.stat().st_size,
           'entries': entries, 'zip_integrity_ok': True, 'cloud_model_calls': 0, 'published': False,
           'byteask_binary_included': False, 'installation': "pip install 'artifacts/proofsmith-0.2.0-py3-none-any.whl[mcp]'; full demos use the repository checkout"}
(config.RESULTS / 'integration-package.json').write_text(json.dumps(receipt, indent=2) + '\n')
print(json.dumps(receipt))
PY
