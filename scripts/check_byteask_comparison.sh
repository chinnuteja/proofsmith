#!/usr/bin/env bash
set -euo pipefail
export DEEPSEEK_API_KEY=""
pytest -q tests/phase9/test_byteask_comparison.py
python scripts/byteask_comparison.py validate --experiment experiments/byteask-comparison/v1
proofsmith protocol validate
