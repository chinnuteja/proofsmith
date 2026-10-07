#!/usr/bin/env bash
set -euo pipefail
export DEEPSEEK_API_KEY=""
python - <<'PY'
# Finalize the zero-model preparation before collecting any real observations.
# The original DeepSeek v5 protocol is never modified by this operation.
import json, sys
from datetime import datetime, timezone
from pathlib import Path
sys.path.insert(0, str(Path.cwd() / 'scripts'))
from byteask_comparison import validate, dump, digest, render
out = Path('experiments/byteask-comparison/v1').resolve()
protocol = validate(out)
summary = json.loads((out / 'offline-results.json').read_text())
assert summary['model_calls'] == 0 and summary['byteask_model_observations'] == 0
if 'frozen_at' in protocol:
    raise RuntimeError('already finalized; choose a new experiment ID for changes')
protocol['frozen_at'] = datetime.now(timezone.utc).isoformat()
protocol['max_additional_spend_usd'] = 0.0
protocol.pop('approved_spend', None)
protocol['usage_policy'] = 'existing free quota only; no purchase, upgrade, top-up or paid fallback'
protocol['decision'] = ('continue only if incorrect acceptances decrease, correct acceptances do not decrease, '
                        'and at least one correct candidate is accepted; otherwise stop or report no advantage')
dump(out / 'protocol.json', protocol)
summary['protocol_sha256'] = digest(out / 'protocol.json')
dump(out / 'offline-results.json', summary)
render(out, summary)
print(json.dumps({'finalized': True, 'protocol_sha256': summary['protocol_sha256'], 'model_calls': 0}))
PY
bash scripts/comparison_preflight.sh experiments/byteask-comparison/v1/account-preflight.json
bash scripts/check_byteask_comparison.sh
