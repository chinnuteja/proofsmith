#!/usr/bin/env bash
set -euo pipefail
# Exercise the real compiler, supplied-check qualification, paired gate and manifests.
# The trivial arithmetic fixture tests integration, not model performance.
root="$(cd "$(dirname "$0")/.." && pwd)"
out="${1:?new output directory outside the example source}"
export DEEPSEEK_API_KEY=""
python - "$root" "$out" <<'PY'
import json, sys
from pathlib import Path
from proofsmith.datasets.schema import BuildRecipe
from proofsmith.gate import seal, check_patch, check_receipt, _copy_source
root, out = map(lambda p: Path(p).resolve(), sys.argv[1:])
out.mkdir(parents=True, exist_ok=False)
repo = root / 'examples/ci-smoke/original'
recipe = BuildRecipe(system='cmake')
sealed = seal(repo, root / 'examples/ci-smoke/harness', recipe, 'assertion', out / 'qualification')
assert sealed['status'] == 'VERIFIED', sealed
_copy_source(repo, out / 'candidate')
(out / 'candidate/calculation.cpp').write_text('int total(int a, int b) { return a + b; }\n')
fixed = check_patch(out / 'qualification/bundle', repo, out / 'candidate', recipe, out / 'fixed', sealed['bundle_id'])
rejected = check_patch(out / 'qualification/bundle', repo, repo, recipe, out / 'unfixed', sealed['bundle_id'])
assert fixed['status'] == 'VERIFIED', fixed
assert rejected['status'] == 'REJECTED', rejected
for name in ('qualification', 'fixed', 'unfixed'):
    check_receipt(out / name)
print(json.dumps({'mode': 'supplied CI fixture; no model', 'fixed': fixed['status'], 'unfixed': rejected['status'], 'output': str(out)}))
PY
