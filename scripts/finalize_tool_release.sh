#!/usr/bin/env bash
set -euo pipefail
cd "${HOME}/proofsmith"
source "${HOME}/.venvs/proofsmith/bin/activate"
export DEEPSEEK_API_KEY=""
pytest -q tests/phase2/test_loop.py tests/phase9/test_patch_gate.py -k 'not real_reference_gate_demo'
python - <<'PY'
from proofsmith.eval.protocol import freeze_protocol, validate_protocol, fingerprint
from proofsmith.eval.runner import write_summary
from proofsmith.report.readme import generate_readme
from proofsmith.report.site import build_site
protocol = freeze_protocol(protocol_id='v4')
validate_protocol(protocol)
write_summary(protocol)
generate_readme()
build_site()
print('Prepared offline protocol', protocol['id'], fingerprint(protocol))
PY
