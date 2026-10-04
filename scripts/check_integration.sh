#!/usr/bin/env bash
set -euo pipefail
export DEEPSEEK_API_KEY=""
exec pytest -q tests/phase9/test_headless_gate.py tests/phase9/test_mcp.py tests/phase9/test_patch_gate.py -k 'not real_reference_gate_demo' "$@"
