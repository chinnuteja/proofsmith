#!/usr/bin/env bash
set -euo pipefail
cd "${HOME}/proofsmith"
git apply --check docs/repairs/token-budget.patch
git apply docs/repairs/token-budget.patch
printf 'Applied the tested repair after the frozen pilot completed; no paid run started.\n'
