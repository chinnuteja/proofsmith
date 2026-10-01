# Contracts

Single source of truth for Proofsmith interfaces.

### Repository layout

```
proofsmith.md                     product spec (exists)
pyproject.toml
.env                              DEEPSEEK_API_KEY (exists, gitignored)
config/pricing.json               DeepSeek prices with source URL + fetch date
proofsmith/
  __init__.py
  config.py                       constants from Global Constraints
  cli.py                          `proofsmith` entrypoint
  toolchain.py                    doctor + probes
  runtime/proofsmith_check.h      PS_CHECK macro for harnesses
  oracles/variants.py             Variant definitions
  oracles/builds.py               build_variant
  oracles/signature.py            parse_evidence
  oracles/runner.py               run_n
  oracles/acceptance.py           decide
  harness.py                      compile_harness
  freeze.py                       freeze / load_bundle / verify_bundle
  datasets/schema.py              Instance, HiddenInstance, BuildRecipe
  datasets/mine.py                Track B candidate mining
  datasets/check.py               dataset validation
  llm.py                          LLMClient, FakeLLM
  ledger.py                       spend ledger
  sandbox.py                      Sandbox
  agent/tools.py                  ToolSet
  agent/loop.py                   run_agent
  prompts/*.md                    all prompts
  pipeline.py                     make_verifier (Proofsmith)
  systems.py                      run_system (b0, b1, proofsmith)
  eval/evaluator.py               evaluate
  eval/alignment.py               changed_functions, align
  eval/runner.py                  resumable eval runner
  eval/metrics.py                 metrics + kill criteria
  report/site.py                  build_site
  report/templates/*.html.j2
  report/static/site.css
  mcp_server.py                   (Phase 9)
cases/<id>/                       demo + micro cases (instance.json, buggy/, hidden/)
data/trackA/{instances,hidden}/
data/trackB/{instances,hidden}/
results/                          committed JSON results
runs/                             trajectories, logs (gitignored)
site/                             generated (gitignored)
scripts/                          ws.ps1, setup_*.sh, gate.sh, browser_gate.{sh,py}, serve.sh, ...
tests/phase<N>/                   tests per phase
tests/fixtures/sanitizer/         real sanitizer outputs (Phase 0)
docs/interfaces.md, docs/claims.md, docs/phase-logs/, docs/evidence/
```

### Instance (visible) — `proofsmith.instance/1`

```json
{
  "schema": "proofsmith.instance/1",
  "id": "orderd-deadlock",
  "track": "demo | micro | A | B",
  "source": {"kind": "dir", "path": "cases/orderd/buggy"},
  "issue": {"title": "...", "body": "...", "url": null, "rewritten": false, "mentions_fix": false},
  "build": {
    "system": "cmake | make | custom",
    "cmake_args": [],
    "targets": [],
    "jobs": 4,
    "custom_script": null,
    "test_command": "ctest --output-on-failure -j4"
  }
}
```

For git-backed instances, `source` is `{"kind": "git", "url": "https://github.com/org/repo", "commit": "<buggy sha>"}`.

### HiddenInstance — `proofsmith.hidden/1`

```json
{
  "schema": "proofsmith.hidden/1",
  "id": "orderd-deadlock",
  "fixed": {"kind": "patch", "path": "cases/orderd/hidden/fix.patch"},
  "bug_class": "deadlock | race | lifetime | ub | behavioral | none",
  "fix_files": ["order_book.cpp"],
  "dev_tests": [],
  "notes": ""
}
```

`fixed.kind` is one of `patch` (applied to the buggy tree), `dir`, or `git` (`{"kind":"git","commit":"<fixed sha>"}`).

### Verifier bundle — `proofsmith.verifier/1`

```
<bundle>/verifier.json
<bundle>/harness/...            exact copy of proofsmith_harness/ at freeze time
```

```json
{
  "schema": "proofsmith.verifier/1",
  "system": "proofsmith | b0 | b1 | reference",
  "instance_id": "orderd-deadlock",
  "status": "accepted | abstained | submitted | gave_up | skipped",
  "abstain_reason": null,
  "oracle": "assertion | asan_ubsan | tsan | null",
  "variant": "plain | asan_ubsan | tsan",
  "signature": "tsan:lock-order-inversion|orderd::OrderBook::cancel@order_book.cpp|...",
  "runtime": {"n": 10, "k": 8, "fails": 10, "signatures": {"<sig>": 10}},
  "files": {"harness/harness.cpp": "<sha256>", "harness/build.sh": "<sha256>"},
  "flags": {"cxxflags": "...", "ldflags": "...", "env": {"TSAN_OPTIONS": "..."}},
  "buggy_tree_sha256": "<hash of snapshot file list + contents>",
  "model": "deepseek-v4-pro",
  "usage": {"prompt_tokens": 0, "completion_tokens": 0, "reasoning_tokens": 0, "cache_hit_tokens": 0},
  "cost_usd": 0.0,
  "wall_s": 0.0,
  "trajectory": "runs/<run_id>/trajectory.jsonl",
  "created_at": "2026-10-01T12:00:00Z"
}
```

### Harness contract (identical for every system)

- The harness lives in `proofsmith_harness/` at the repo root. Nothing outside it may be created, modified or deleted. Violations invalidate the run.
- `proofsmith_harness/build.sh` is run as `bash proofsmith_harness/build.sh` with cwd = repo root and env:
  - `PS_REPO` absolute repo path; `PS_BUILD_DIR` the project's build dir for the chosen variant; `PS_COMPILE_COMMANDS` path to `compile_commands.json`;
  - `PS_CC=clang`, `PS_CXX=clang++`, `PS_CXXFLAGS` and `PS_LDFLAGS` for the variant; `PS_INCLUDE` dir containing `proofsmith_check.h`;
  - `PS_OUT` output dir. It must produce the executable `$PS_OUT/harness` and exit 0.
- The harness is run as `$PS_OUT/harness` with no args, cwd = repo root, the variant's runtime env, and timeout `RUN_TIMEOUT_S`.
- **Fail** = non-zero exit code, a signal, or a timeout. **Pass** = exit 0 within the timeout.

### Evidence and signature

- `Frame(index:int, function:str, file:str, line:int)`; `file` is an absolute path.
- `Evidence(kind:str, frames:list[Frame], app_frames:list[Frame], signature:str)`.
- `kind` values: `asan:<slug>`, `ubsan:<slug>`, `tsan:<slug>`, `assert`, `timeout`, `crash:<SIGNAME>`, `exit:<code>`, `none`.
- An **app frame** is a frame whose `file` is under `repo_root` and not under `repo_root/proofsmith_harness`.
- Sanitizer signature: `"<kind>|" + "|".join(f"{normalize_function(f.function)}@{relpath(f.file, repo_root)}" for f in app_frames[:3])`. Line numbers are deliberately excluded.
- Assertion signature: `"assert|<relpath>:<line>"`.
- `timeout`, `exit:<code>`, `crash:<SIG>` and `none` signatures are just their kind.

### Results JSON

- `results/demo/orderd.json` (Phase 1, extended in Phase 3)
- `results/verifiers/<instance_id>/<system>.json` (copy of verifier.json; Phases 3, 5, 6)
- `results/eval/<track>/<instance_id>/<system>.json` (Verdict; Phases 5, 6)
- `results/summary.json` (metrics; Phase 6)

Verdict — `proofsmith.verdict/1`:

```json
{
  "schema": "proofsmith.verdict/1",
  "instance_id": "...", "system": "b1", "track": "B",
  "bundle_status": "submitted",
  "build_ok_buggy": true, "build_ok_fixed": true,
  "buggy_fails": 20, "fixed_fails": 0, "n": 20,
  "f2p": true,
  "alignment": {"strict": true, "relaxed": true, "unknown": false, "hits": [{"function": "...", "file": "...", "via": "frame|coverage"}]},
  "oracle": "tsan", "evidence_kinds": {"tsan:lock-order-inversion": 20},
  "cost_usd": 0.0, "wall_s": 0.0, "error": null
}
```

`f2p = build_ok_buggy and build_ok_fixed and buggy_fails >= EVAL_BUGGY_K and fixed_fails <= EVAL_FIXED_MAX_FAILS`.
