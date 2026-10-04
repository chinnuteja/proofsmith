#!/usr/bin/env bash
set -euo pipefail
cd "${HOME}/proofsmith"
source "${HOME}/.venvs/proofsmith/bin/activate"
export DEEPSEEK_API_KEY=""
pytest -q tests/phase2/test_loop.py tests/phase9/test_patch_gate.py -k 'not real_reference_gate_demo'
pytest -q tests/phase9/test_mcp.py
