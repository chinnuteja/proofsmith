#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
export BYTEASK_HOME="$PWD/.tools/byteask-home"
export BYTEASK_NO_UPDATE_CHECK=1
mkdir -p "$BYTEASK_HOME"
binary="$PWD/.tools/byteask/byteask-engine"
"$binary" mcp add proofsmith --env "PROOFSMITH_ALLOW_GENERATION=0" --env "DEEPSEEK_API_KEY=" \
  --env "PROOFSMITH_RESULTS_DIR=$PWD/results" -- "$(command -v python)" -m proofsmith.mcp_server
python - <<'PY'
import os, tomllib
from pathlib import Path
path = Path(os.environ['BYTEASK_HOME']) / 'config.toml'
text = path.read_text()
server = tomllib.loads(text)['mcp_servers']['proofsmith']
extras = ''
for key, value in [('startup_timeout_sec', 30), ('tool_timeout_sec', 600)]:
    if key not in server:
        extras += f'{key} = {value}\n'
text = text.replace('[mcp_servers.proofsmith]\n', '[mcp_servers.proofsmith]\n' + extras, 1)
path.write_text(text)
print('Proofsmith registered; tool timeout 600 seconds; generation disabled.')
PY
"$binary" mcp list --json
