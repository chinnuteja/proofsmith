#!/usr/bin/env bash
set -euo pipefail
cd ~/proofsmith
source ~/.venvs/proofsmith/bin/activate
pytest -q tests/phase2/test_live_smoke.py -m live
proofsmith ledger status
