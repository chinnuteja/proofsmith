#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")/.."
for tool in python clang clang++ cmake ninja ctags bwrap llvm-cov llvm-profdata; do
  command -v "$tool" >/dev/null || { echo "Missing dependency: $tool" >&2; exit 2; }
done
export PYTHONPATH="$PWD${PYTHONPATH:+:$PYTHONPATH}"
if [[ "${1:-}" == "--with-agents" ]]; then
  python - <<'PY'
import json
from proofsmith.eval.protocol import PROTOCOL_PATH
from proofsmith.eval.preflight import estimate
print(json.dumps(estimate(json.loads(PROTOCOL_PATH.read_text())), indent=2))
PY
  exec python -m proofsmith.cli evaluate
fi
if [[ $# != 0 ]]; then echo "Usage: reproduce.sh [--with-agents]" >&2; exit 2; fi
export DEEPSEEK_API_KEY=""
python - <<'PY'
import json
from proofsmith import config
from proofsmith.demo import run_orderd
from proofsmith.eval.runner import atomic_json
path = config.RESULTS / "demo/orderd.json"
previous = json.loads(path.read_text()) if path.exists() else None
try:
    run_orderd()
    current = json.loads(path.read_text())
    atomic_json(config.RESULTS / "replay/demo-orderd.json", current)
    if previous is None or current["rows"] != previous["rows"]:
        raise SystemExit("demo outcome differs from the stored matrix; inspect results/replay/demo-orderd.json")
finally:
    if previous is not None:
        atomic_json(path, previous)
PY
python -m proofsmith.cli replay --check
