#!/usr/bin/env bash
set -euo pipefail
export DEEPSEEK_API_KEY=""
exec python scripts/check_integration_browser.py
