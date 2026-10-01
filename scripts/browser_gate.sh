#!/usr/bin/env bash
set -euo pipefail
N="${1:?phase number}"
cd ~/proofsmith
source ~/.venvs/proofsmith/bin/activate
proofsmith report build
bash scripts/serve.sh
python scripts/browser_gate.py --phase "$N"
