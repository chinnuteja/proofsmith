#!/usr/bin/env bash
set -euo pipefail
cd "${HOME}/proofsmith"
source "${HOME}/.venvs/proofsmith/bin/activate"
export DEEPSEEK_API_KEY="OFFLINE_TEST_SENTINEL"
pytest -q -m 'not live' tests/phase2/test_loop.py tests/phase3/test_classify.py tests/phase3/test_pipeline_fake.py tests/phase5/test_systems_fake.py tests/phase6/test_token_reservation.py tests/phase6/test_protocol_versions.py tests/phase6/test_runner.py tests/phase7/test_reporting.py
