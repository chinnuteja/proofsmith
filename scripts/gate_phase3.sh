#!/usr/bin/env bash
set -euo pipefail
cd ~/proofsmith
source ~/.venvs/proofsmith/bin/activate

ids=(orderd-deadlock uaf-lru race-stats ub-notional rounding-ticks vague-perf)
rerun=0
for arg in "$@"; do
  if [[ "${arg}" == "--rerun" ]]; then
    rerun=1
  fi
done

missing=0
for id in "${ids[@]}"; do
  if [[ ! -f "results/verifiers/${id}/proofsmith.json" ]]; then
    missing=1
  fi
done

if [[ "${missing}" -eq 1 || "${rerun}" -eq 1 ]]; then
  if [[ "${rerun}" -eq 1 ]]; then
    export PROOFSMITH_RERUN=1
  else
    unset PROOFSMITH_RERUN || true
  fi
  pytest -q tests/phase3/test_live_pipeline.py -m live
fi

python3 - << 'PY'
from proofsmith.demo import run_orderd
run_orderd()
PY

proofsmith ledger status
