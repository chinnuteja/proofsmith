#!/usr/bin/env bash
set -uo pipefail
N="${1:?phase number}"
cd ~/proofsmith
source ~/.venvs/proofsmith/bin/activate
fail=0
echo "== pytest tests/phase0..phase${N}"
dirs=""; for i in $(seq 0 "$N"); do [ -d "tests/phase$i" ] && dirs="$dirs tests/phase$i"; done
pytest -q $dirs -m "not live" || fail=1
if [ -f "scripts/gate_phase${N}.sh" ]; then echo "== phase-specific checks"; bash "scripts/gate_phase${N}.sh" || fail=1; fi
echo "== no case-specific prompt tuning"
bash scripts/check_no_tuning.sh || fail=1
echo "== browser gate"
bash scripts/browser_gate.sh "$N" || fail=1
if [ "$fail" -eq 0 ]; then echo "GATE ${N}: PASS"; else echo "GATE ${N}: FAIL"; exit 1; fi
