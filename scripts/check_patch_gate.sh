#!/usr/bin/env bash
set -euo pipefail
cd "${HOME}/proofsmith"
source "${HOME}/.venvs/proofsmith/bin/activate"
exec pytest -q tests/phase9/test_patch_gate.py tests/phase9/test_mcp.py "$@"
