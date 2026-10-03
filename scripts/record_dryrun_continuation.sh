#!/usr/bin/env bash
set -euo pipefail
cd "${HOME}/proofsmith"
source "${HOME}/.venvs/proofsmith/bin/activate"
python - <<'PY'
import json
from proofsmith import config
from proofsmith.ledger import Ledger, LEDGER_PATH
names = ('rounding-ticks', 'vague-perf')
rows = []
for name in names:
    for system in ('b0', 'b1'):
        path = config.RESULTS / 'dryrun' / name / f'{system}.json'
        value = json.loads(path.read_text())
        assert value['schema'] == 'proofsmith.verdict/1'
        rows.append((path.relative_to(config.REPO).as_posix(), value))
text = '# Authorized dry-run continuation — 2026-10-03\n\n'
text += 'Four missing observations were generated using the approved DeepSeek payload transfer and existing global cap. These are plumbing dry-runs, separate from frozen-protocol experiment observations. The original Phase 5 historical ceiling failure is retained.\n\n'
text += '| Instance | System | Buggy failures | Fixed failures | Raw F→P | Strict alignment | Cost USD | Source |\n|---|---|---:|---:|---|---|---:|---|\n'
for path, value in rows:
    text += f"| {value['instance_id']} | {value['system']} | {value['buggy_fails']}/{value['n']} | {value['fixed_fails']}/{value['n']} | {value['f2p']} | {value['alignment']['strict']} | {value['cost_usd']:.9f} | [{path}](../../{path}) |\n"
spent = Ledger(LEDGER_PATH).spent_usd()
text += f'\nNew dry-run generation cost: ${sum(v["cost_usd"] for _, v in rows):.9f}. Total recorded ledger spend: ${spent:.9f}. Remaining under ${config.MAX_USD:.2f}: ${config.MAX_USD-spent:.9f}.\n'
(config.REPO / 'docs/phase-logs/dryrun-continuation-2026-10-03.md').write_text(text)
print(text)
PY
