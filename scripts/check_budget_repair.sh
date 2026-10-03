#!/usr/bin/env bash
set -euo pipefail
cd "${HOME}/proofsmith/scratch/budget-repair"
source "${HOME}/.venvs/proofsmith/bin/activate"
export PYTHONPATH="$PWD"
export DEEPSEEK_API_KEY="OFFLINE_TEST_SENTINEL"
pytest -q -m 'not live' tests/phase2/test_loop.py tests/phase3/test_classify.py tests/phase3/test_pipeline_fake.py tests/phase5/test_systems_fake.py tests/phase6/test_token_reservation.py
