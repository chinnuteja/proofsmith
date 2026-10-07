#!/usr/bin/env bash
set -euo pipefail
export DEEPSEEK_API_KEY=""
python - "${1:-}" <<'PY'
import json, os, subprocess
import re
import sys
from pathlib import Path
root = Path.cwd()
binary = root / '.tools/byteask/byteask-engine'
rows = []
for name, home in [('project', root / '.tools/byteask-home'), ('default', Path.home() / '.byteask')]:
    env = dict(os.environ, BYTEASK_HOME=str(home), BYTEASK_NO_UPDATE_CHECK='1')
    result = subprocess.run([str(binary), 'login', 'status'], env=env, capture_output=True, text=True, timeout=30)
    status = (result.stdout + result.stderr).lower()
    authenticated = result.returncode == 0 and 'logged in' in status and 'not logged in' not in status
    # The managed ByteAsk gateway uses config-based auth, distinct from the
    # engine's upstream login store. Report field presence only, never values.
    cfg = home / 'config.toml'
    credential_configured = False
    if cfg.is_file():
        with cfg.open() as handle:
            credential_configured = any(re.match(r'^experimental_bearer_token\s*=', line) for line in handle)
    rows.append({'profile': name, 'engine_authenticated': authenticated,
                 'managed_credential_configured': credential_configured,
                 'status_exit_code': result.returncode})
record = {'schema': 'proofsmith.byteask-comparison-preflight/1', 'model_requests': 0, 'profiles': rows}
if sys.argv[1]:
    out = Path(sys.argv[1]).resolve()
    if not out.is_relative_to(root.resolve()):
        raise ValueError('preflight output must stay inside the project')
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(record, indent=2) + '\n')
print(json.dumps(record, indent=2))
PY
