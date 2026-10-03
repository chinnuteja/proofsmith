#!/usr/bin/env bash
set -euo pipefail
cd "${HOME}/proofsmith"
source "${HOME}/.venvs/proofsmith/bin/activate"
python - <<'PY'
import hashlib
import json
from proofsmith import config
from proofsmith.eval.replay import outcome
from proofsmith.eval.runner import atomic_json
summary = json.loads((config.RESULTS / 'replay_summary.json').read_text())
records = [r for r in summary['records'] if not r['matches']]
expected = {('uaf-lru', 'b0'), ('uaf-lru', 'b1'), ('uaf-lru', 'proofsmith'), ('rounding-ticks', 'proofsmith')}
assert {(r['previous']['instance_id'], r['previous']['system']) for r in records} == expected
changes = []
for row in records:
    path = config.REPO / row['stored']
    previous_bytes = path.read_bytes()
    previous = json.loads(previous_bytes)
    assert outcome(previous) == row['previous'], 'reference changed since replay'
    rel = row['bundle'].removeprefix('results/')
    replay = config.RESULTS / 'replay' / rel / 'verdict.json'
    recomputed = json.loads(replay.read_text())
    assert outcome(recomputed) == row['recomputed']
    assert {k:v for k,v in outcome(previous).items() if k != 'alignment'} == {k:v for k,v in outcome(recomputed).items() if k != 'alignment'}
    archived = config.RESULTS / 'history/evaluator-v0' / path.relative_to(config.RESULTS)
    archived.parent.mkdir(parents=True, exist_ok=True)
    if archived.exists():
        assert archived.read_bytes() == previous_bytes
    else:
        archived.write_bytes(previous_bytes)
    corrected = {**previous, 'alignment': recomputed['alignment'],
                 'evaluator_revision': '4fff7ffa35ab9b27b413337fb2a10923c1991382',
                 'previous_verdict': archived.relative_to(config.REPO).as_posix()}
    atomic_json(path, corrected)
    changes.append({'path': row['stored'], 'archive': archived.relative_to(config.REPO).as_posix(),
                    'old_sha256': hashlib.sha256(previous_bytes).hexdigest(),
                    'new_sha256': hashlib.sha256(path.read_bytes()).hexdigest(),
                    'previous_alignment': previous['alignment'], 'corrected_alignment': recomputed['alignment'],
                    'raw_outcome_unchanged': True})
atomic_json(config.RESULTS / 'alignment_migration.json', {'schema': 'proofsmith.alignment-migration/1',
    'evaluator_revision': '4fff7ffa35ab9b27b413337fb2a10923c1991382',
    'reason': 'Replace context-line and broken-coverage alignment references with actual audited corrected-evaluator replay. Preserve original bytes and all raw outcomes.', 'changes': changes})
print('Four corrected alignment references saved; original bytes archived; all raw outcomes unchanged.')
PY
