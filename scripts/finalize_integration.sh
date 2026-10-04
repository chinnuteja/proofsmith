#!/usr/bin/env bash
set -euo pipefail
export DEEPSEEK_API_KEY=""
python -m pip wheel --no-deps . -w artifacts
python - <<'PY'
import json
from proofsmith.eval.protocol import freeze_protocol, validate_protocol, fingerprint
from proofsmith.eval.runner import write_summary
from proofsmith.report.readme import generate_readme
from proofsmith.report.site import build_site
protocol = freeze_protocol(protocol_id='v5')
validate_protocol(protocol)
write_summary(protocol)
generate_readme()
build_site()
print(json.dumps({'protocol_id': protocol['id'], 'sha256': fingerprint(protocol), 'model_calls': 0}))
PY
pytest -q tests/phase0/test_config.py tests/phase0/test_site.py tests/phase7/test_reporting.py
