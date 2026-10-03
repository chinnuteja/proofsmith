#!/usr/bin/env bash
set -euo pipefail
cd "${HOME}/proofsmith"
source "${HOME}/.venvs/proofsmith/bin/activate"
python - <<'PY'
import json
from collections import Counter
from proofsmith import config
from proofsmith.eval.protocol import PROTOCOL_PATH, fingerprint
from proofsmith.eval.runner import atomic_json, read_rows
protocol = json.loads(PROTOCOL_PATH.read_text())
rows = read_rows(protocol)
cost = json.loads((config.RESULTS / 'pilot_cost.json').read_text())
audit = json.loads((config.RESULTS / 'pilot_budget_audit.json').read_text())
assert cost['complete'] and len(rows) == 12
assert cost['protocol_sha256'] == audit['protocol_sha256'] == fingerprint(protocol)
value = {'schema': 'proofsmith.pilot-findings/1', 'protocol_id': protocol['id'],
    'protocol_sha256': fingerprint(protocol), 'observations': len(rows),
    'raw_f2p_count': sum(bool(r['f2p']) for r in rows),
    'pilot_generation_cost_usd': sum(r['cost_usd'] for r in rows),
    'recorded_spend_usd': cost['recorded_spend_usd'], 'remaining_cap_usd': cost['remaining_cap_usd'],
    'projected_remaining_under_old_code_usd': cost['projected_remaining_usd'],
    'budget_violations': len(audit['violations']), 'strict_budget_valid': not audit['violations'],
    'full_run_authorized': False, 'paid_execution_stopped': True,
    'status_counts': dict(Counter(r['bundle_status'] for r in rows))}
atomic_json(config.RESULTS / 'pilot_findings.json', value)
text = f"""# Pilot outcome — {protocol['id']}

The approved pilot completed all {len(rows)} observations. Paid execution stopped afterward. No full experiment or additional paid protocol has started.

Raw fail-to-pass successes: {value['raw_f2p_count']}. Proofsmith abstained on every pilot case; the baselines either gave up or submitted harnesses that did not pass the hidden fixed-tree evaluation. These are negative pilot outcomes, not a complete benchmark verdict.

Pilot generation cost: ${value['pilot_generation_cost_usd']:.9f}. Total recorded spend: ${cost['recorded_spend_usd']:.9f}. Remaining under the approved global cap: ${cost['remaining_cap_usd']:.9f}. The old-code estimate for the remaining experiment is ${cost['projected_remaining_usd']:.9f}, including the safety multiplier. This projection must be remeasured after the repair and does not authorize spending.

The usage audit found {len(audit['violations'])} final-request token overruns. The original code checked usage after a response. A tested repair now reserves input and completion before requests; its stronger guard is conservative and applies to all systems. The prior protocol, its source commit, verdicts and cost/audit snapshots are retained. A new protocol is prepared offline before any proposed rerun.

Sources: [findings JSON](../../results/pilot_findings.json), [cost JSON](../../results/protocol-history/{protocol['id']}/pilot_cost.json), [usage audit](../../results/protocol-history/{protocol['id']}/pilot_budget_audit.json), [verdicts](../../results/eval/{protocol['id']}), [repair](../repairs/README.md).

The next paid action requires user authorization at the plan's pilot stop. A full comparison remains blocked until a matching completed pilot and clean budget audit exist under the repaired protocol, plus explicit full-run budget approval.
"""
(config.REPO / 'docs/phase-logs/pilot-outcome-2026-10-03.md').write_text(text)
print(json.dumps(value, indent=2))
PY
