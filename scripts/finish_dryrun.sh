#!/usr/bin/env bash
set -euo pipefail
cd "${HOME}/proofsmith"
source "${HOME}/.venvs/proofsmith/bin/activate"
pytest -q tests/phase5/test_live_baselines.py -s
proofsmith report build
