#!/usr/bin/env bash
set -euo pipefail
cd ~/proofsmith
source ~/.venvs/proofsmith/bin/activate
export GIT_TERMINAL_PROMPT=0
python - << 'PY'
import json
import subprocess
import sys

proc = subprocess.run(
    [
        "curl",
        "-sS",
        "-H",
        "Accept: application/vnd.github+json",
        "-H",
        "User-Agent: proofsmith",
        "https://api.github.com/rate_limit",
    ],
    stdout=subprocess.PIPE,
    stderr=subprocess.STDOUT,
    check=False,
    text=True,
)
if proc.returncode != 0:
    print(proc.stdout)
    print("RATE_LIMIT_CHECK_FAIL")
    sys.exit(1)
payload = json.loads(proc.stdout)
core = payload.get("resources", {}).get("core", {})
print(
    f"RATE remaining={core.get('remaining')} limit={core.get('limit')} reset={core.get('reset')}",
    flush=True,
)
remaining = int(core.get("remaining") or 0)
if remaining <= 0:
    print("RATE_LIMIT remaining=0")
    sys.exit(2)
PY
python -m proofsmith.datasets.mine "$@"
