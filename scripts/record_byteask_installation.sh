#!/usr/bin/env bash
set -euo pipefail
python - <<'PY'
import hashlib, json, subprocess
from pathlib import Path
root = Path('.tools/byteask')
asset = 'byteask-engine-linux-x86_64.xz'
expected = next(line.split()[0] for line in (root / 'SHA256SUMS').read_text().splitlines() if line.split()[1].lstrip('*') == asset)
digest = hashlib.sha256((root / asset).read_bytes()).hexdigest()
assert digest == expected
receipt = {'schema': 'proofsmith.byteask-installation/1', 'release_tag': 'v0.1.15',
           'asset_sha256': digest, 'release_checksum_matches': True,
           'engine_sha256': hashlib.sha256((root / 'byteask-engine').read_bytes()).hexdigest(),
           'launcher_sha256': hashlib.sha256((root / 'byteask').read_bytes()).hexdigest(),
           'binary_version': subprocess.check_output([str(root / 'byteask-engine'), '--version'], text=True).strip(),
           'scope': 'project local installation; no login or model call', 'binary_redistributed': False}
Path('results/byteask-installation.json').write_text(json.dumps(receipt, indent=2) + '\n')
print(json.dumps(receipt))
PY
