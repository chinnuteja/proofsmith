#!/usr/bin/env bash
set -euo pipefail
cd "${HOME}/proofsmith"
source "${HOME}/.venvs/proofsmith/bin/activate"
export DEEPSEEK_API_KEY=""
python - <<'PY'
import hashlib
import json
import shutil
import zipfile
from pathlib import Path
from proofsmith import config
from proofsmith.gate import check_receipt
from proofsmith.report.readme import generate_readme
from proofsmith.report.site import build_site
root = config.RESULTS / 'tool-demo'
transcript = json.loads((config.RESULTS / 'integration/reference_transcript.json').read_text())
source = Path(transcript['patch_gate']['receipt_path']).parent
shutil.copytree(source, root / 'mcp', dirs_exist_ok=True)
for manifest in root.rglob('manifest.json'):
    check_receipt(manifest.parent)
generate_readme()
build_site()
artifacts = config.REPO / 'artifacts'
artifacts.mkdir(exist_ok=True)
archive = artifacts / 'proofsmith-verification-demo.zip'
with zipfile.ZipFile(archive, 'w', zipfile.ZIP_DEFLATED) as package:
    for path in sorted(root.rglob('*')):
        if path.is_file():
            package.write(path, path.relative_to(root).as_posix())
    package.write(config.REPO / 'docs/verification-tool.md', 'GUIDE.md')
    package.write(config.RESULTS / 'tool-diagnostics/pilot-v1.json', 'pilot-diagnosis.json')
with zipfile.ZipFile(archive) as package:
    assert package.testzip() is None
receipt = {'schema': 'proofsmith.tool-package/1', 'path': str(archive.relative_to(config.REPO)),
           'sha256': hashlib.sha256(archive.read_bytes()).hexdigest(), 'bytes': archive.stat().st_size,
           'entries': len(package.namelist()), 'zip_integrity_ok': True,
           'model_calls': 0, 'published': False}
(config.RESULTS / 'tool-package.json').write_text(json.dumps(receipt, indent=2) + '\n')
print(json.dumps(receipt))
PY
