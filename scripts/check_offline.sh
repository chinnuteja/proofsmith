#!/usr/bin/env bash
set -euo pipefail
cd "${HOME}/proofsmith"
source "${HOME}/.venvs/proofsmith/bin/activate"
pytest -q -m 'not live' \
  tests/phase0/test_config.py tests/phase0/test_site.py \
  tests/phase1/test_acceptance.py tests/phase1/test_signature.py tests/phase1/test_freeze.py tests/phase1/test_builds.py \
  tests/phase2/test_ledger.py tests/phase2/test_llm_fake.py tests/phase2/test_loop.py tests/phase2/test_tools.py tests/phase2/test_sandbox.py \
  tests/phase3/test_classify.py tests/phase3/test_pipeline_fake.py \
  tests/phase4/test_schema.py tests/phase4/test_separation.py \
  tests/phase5/test_alignment.py tests/phase5/test_evaluator_regressions.py tests/phase5/test_evaluator.py tests/phase5/test_systems_fake.py \
  tests/phase6 tests/phase7 tests/phase9
