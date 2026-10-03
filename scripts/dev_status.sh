#!/usr/bin/env bash
set -euo pipefail
df -h / /mnt/c
for tool in bwrap ctags clang llvm-cov llvm-profdata; do
  command -v "$tool" || true
done
python - <<'PY'
from proofsmith.ledger import Ledger, LEDGER_PATH
from proofsmith.config import MAX_USD
ledger = Ledger(LEDGER_PATH)
print(f"Recorded spend ${ledger.spent_usd():.6f}; cap ${MAX_USD:.2f}")
PY
