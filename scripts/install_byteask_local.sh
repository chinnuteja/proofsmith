#!/usr/bin/env bash
set -euo pipefail
# Local tools only: no installer execution, login, model call, shell-profile or gdb edits.
cd "$(dirname "$0")/.."
mkdir -p .tools/byteask
release=v0.1.15
base="https://github.com/ByteAsk/cli/releases/download/$release"
asset=byteask-engine-linux-x86_64.xz
curl -fsSL --connect-timeout 20 --max-time 600 "$base/SHA256SUMS" -o .tools/byteask/SHA256SUMS
curl -fsSL --connect-timeout 20 --max-time 600 "$base/$asset" -o ".tools/byteask/$asset"
(cd .tools/byteask && awk '$2 == "byteask-engine-linux-x86_64.xz" {print}' SHA256SUMS | sha256sum -c -)
xz -dc ".tools/byteask/$asset" > .tools/byteask/byteask-engine
curl -fsSL --connect-timeout 20 --max-time 60 https://code.byteask.ai/byteask -o .tools/byteask/byteask
head -n1 .tools/byteask/byteask | grep -q '^#!'
chmod +x .tools/byteask/byteask .tools/byteask/byteask-engine
export BYTEASK_HOME="$PWD/.tools/byteask-home"
export BYTEASK_NO_UPDATE_CHECK=1
mkdir -p "$BYTEASK_HOME"
.tools/byteask/byteask-engine --version
python - <<'PY'
import hashlib, json
from pathlib import Path
root = Path('.tools/byteask')
receipt = {'release_tag': 'v0.1.15', 'asset_sha256': hashlib.sha256((root / 'byteask-engine-linux-x86_64.xz').read_bytes()).hexdigest(),
           'engine_sha256': hashlib.sha256((root / 'byteask-engine').read_bytes()).hexdigest(),
           'launcher_sha256': hashlib.sha256((root / 'byteask').read_bytes()).hexdigest(), 'scope': 'project local; no login or model call'}
(root / 'installation.json').write_text(json.dumps(receipt, indent=2) + '\n')
print(json.dumps(receipt))
PY
