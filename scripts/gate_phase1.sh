#!/usr/bin/env bash
set -euo pipefail
cd ~/proofsmith
source ~/.venvs/proofsmith/bin/activate
python - << 'PY'
import json
from pathlib import Path

import jsonschema

root = Path(".")
schema = json.loads((root / "tests/phase1/demo.schema.json").read_text(encoding="utf-8"))
data = json.loads((root / "results/demo/orderd.json").read_text(encoding="utf-8"))
jsonschema.validate(data, schema)
print("orderd.json: schema OK")
PY
