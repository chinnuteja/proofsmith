#!/usr/bin/env bash
set -euo pipefail
issue="${1:?issue JSON with title and body}"
task="${2:?patch task}"
command -v byteask >/dev/null || { echo "byteask executable missing; install and sign in before a real gated run." >&2; exit 2; }
python - "$issue" "$task" "$PWD" <<'PY'
import sys
from pathlib import Path
from proofsmith.integration import gated_run
raise SystemExit(gated_run(Path(sys.argv[1]), sys.argv[2], Path(sys.argv[3])))
PY
