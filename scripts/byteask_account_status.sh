#!/usr/bin/env bash
set -euo pipefail
python - <<'PY'
import json, tomllib, urllib.request, urllib.error
from pathlib import Path
root = Path.cwd()
cfg = tomllib.loads((root / '.tools/byteask-home/config.toml').read_text())
provider = cfg.get('model_providers', {}).get('byteask', {})
base = provider.get('base_url', '').rstrip('/')
if base != 'https://code.byteask.ai/byteask/v1':
    raise RuntimeError('account status only supports the official ByteAsk managed gateway')
token = provider.get('experimental_bearer_token')
if not token:
    raise RuntimeError('no managed sign-in credential configured')
record = {'model_requested': cfg.get('model'), 'provider': cfg.get('model_provider'), 'model_calls': 0, 'endpoints': {}}
for name in ('model-access', 'usage'):
    req = urllib.request.Request(base + '/' + name, headers={'Authorization': 'Bearer ' + token})
    try:
        with urllib.request.urlopen(req, timeout=15) as response:
            data = json.load(response)
        # Report field names and selected non-credential account/model facts only.
        safe = {'ok': True, 'fields': sorted(data)}
        for key in ('locked', 'inactive', 'plan', 'balance', 'remaining', 'credits', 'credits_remaining',
                    'used', 'limit', 'usage', 'usage_limit', 'usd_balance', 'plan_expires_at',
                    'extra_balance_usd', 'extra_granted_usd', 'extra_spent_usd',
                    'used_5h_pct', 'used_week_pct', 'reset_5h_sec', 'reset_week_sec'):
            if key in data:
                safe[key] = data[key]
        record['endpoints'][name] = safe
    except urllib.error.HTTPError as exc:
        record['endpoints'][name] = {'ok': False, 'http_status': exc.code}
    except (urllib.error.URLError, TimeoutError, ValueError) as exc:
        record['endpoints'][name] = {'ok': False, 'error_type': type(exc).__name__}
(root / '.tools/byteask-comparison-account.json').write_text(json.dumps(record, indent=2) + '\n')
print(json.dumps(record, indent=2))
PY
