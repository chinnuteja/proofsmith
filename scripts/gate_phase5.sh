#!/usr/bin/env bash
set -euo pipefail
cd "${HOME}/proofsmith"
source "${HOME}/.venvs/proofsmith/bin/activate"

ids=(orderd-deadlock uaf-lru race-stats ub-notional rounding-ticks vague-perf)
systems=(b0 b1 proofsmith)
rerun=0
for arg in "$@"; do
  if [[ "${arg}" == "--rerun" ]]; then
    rerun=1
  fi
done

missing=0
for id in "${ids[@]}"; do
  for system in "${systems[@]}"; do
    if [[ ! -f "results/dryrun/${id}/${system}.json" ]]; then
      missing=1
    fi
  done
done

if [[ "${missing}" -eq 1 || "${rerun}" -eq 1 ]]; then
  if [[ "${rerun}" -eq 1 ]]; then
    export PROOFSMITH_RERUN=1
  else
    unset PROOFSMITH_RERUN || true
  fi
  pytest -q tests/phase5/test_live_baselines.py -m live
fi

proofsmith report build
proofsmith ledger status
