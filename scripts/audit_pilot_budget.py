"""Check actual frozen usage against the protocol without changing observations."""
import json

from proofsmith import config
from proofsmith.eval.protocol import PROTOCOL_PATH, fingerprint
from proofsmith.eval.runner import atomic_json, result_root

protocol = json.loads(PROTOCOL_PATH.read_text())
records = []
for pair in protocol['order']:
    if pair['instance_id'] not in protocol['pilot'][pair['track']]:
        continue
    path = result_root(protocol) / pair['track'] / pair['instance_id'] / pair['system'] / 'verifier.json'
    if not path.is_file():
        continue
    meta = json.loads(path.read_text())
    usage = meta.get('usage') or {}
    tokens = usage.get('prompt_tokens', 0) + usage.get('completion_tokens', 0)
    maximum = protocol['budget']['max_total_tokens']
    records.append({**pair, 'total_tokens': tokens, 'max_total_tokens': maximum,
                    'token_overrun': max(0, tokens - maximum),
                    'wall_s': meta.get('wall_s', 0),
                    'wall_overrun_s': max(0, meta.get('wall_s', 0) - protocol['budget']['max_wall_s'])})
violations = [r for r in records if r['token_overrun'] or r['wall_overrun_s']]
value = {'schema': 'proofsmith.budget-audit/1', 'protocol_sha256': fingerprint(protocol),
         'observed_bundles': len(records), 'expected_bundles': sum(map(len, protocol['pilot'].values())) * 3,
         'violations': violations, 'records': records,
         'limitation': 'The current agent loop checks token usage after a response; its final request can overshoot the nominal token limit. Do not claim a strict hard token cap or advance a full experiment until this is repaired under a new frozen protocol.' if violations else None}
atomic_json(config.RESULTS / 'pilot_budget_audit.json', value)
print(json.dumps(value, indent=2))
