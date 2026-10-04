#!/usr/bin/env bash
set -euo pipefail
cd "${HOME}/proofsmith"
source "${HOME}/.venvs/proofsmith/bin/activate"
export DEEPSEEK_API_KEY=""
case "${1:-}" in
  demo|seal|gate|bundle-id|evidence-check|report|metrics|protocol) exec proofsmith "$@" ;;
  *) echo "Offline wrapper: command not allowed" >&2; exit 2 ;;
esac
