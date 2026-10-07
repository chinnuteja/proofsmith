#!/usr/bin/env bash
set -euo pipefail
export DEEPSEEK_API_KEY=""
pytest -q tests/phase9/test_byteask_live_policy.py
python scripts/byteask_comparison_live.py --isolation-check
