#!/usr/bin/env bash
set -euo pipefail
export DEEPSEEK_API_KEY=""
exec python scripts/report_byteask_comparison.py "$@"
