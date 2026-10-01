# Proofsmith Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan phase-by-phase. Steps use checkbox (`- [ ]`) syntax for tracking. You execute **one phase per session**, then stop at that phase's gate.

**Goal:** Build Proofsmith: given a C/C++ bug report and the buggy repo (never the fix), it constructs a toolchain-backed failing check (assertion, ASan+UBSan, or TSan), validates it statistically, freezes it, or abstains with a reason. Then prove, against a strong same-model baseline, whether that beats "reproduce first, sanitizers are available".

**Architecture:** A Python orchestrator (`proofsmith/`) drives clang 18 builds inside WSL2 Ubuntu 24.04. A minimal tool-calling agent loop (DeepSeek, OpenAI-compatible API) writes a harness as a *new* target in `proofsmith_harness/` inside a network-isolated, history-free snapshot of the buggy repo. Deterministic code, not the model, decides acceptance (k-of-n with a stable failure signature), freezes the verifier bundle (sha256 manifest), and a hidden evaluator runs bundles against fixed commits. A static HTML site renders every artifact so each phase can be checked in a browser.

**Tech Stack:** WSL2 Ubuntu 24.04, clang/clang++ 18.1.3, CMake 3.28, Ninja, LLVM tools (llvm-symbolizer, llvm-cov, llvm-profdata, llvm-cxxfilt), universal-ctags, Python 3.12 (openai SDK, pydantic v2, jinja2, pytest, playwright), DeepSeek API (`deepseek-v4-pro`, `deepseek-flash`).

---

## How to use this document

- **Orchestrator** (the Claude session that wrote this plan) dispatches one executor per phase, reviews the gate output, the phase log and the screenshots, and only then dispatches the next phase.
- **Executor** (Grok 4.7, xhigh) reads: *Global Constraints*, *Executor Rules*, *Contracts*, and **only its own phase**. Each phase restates the interfaces it consumes; do not rely on memory of earlier phases.
- **Source documents:** `proofsmith.md` (the product spec, at the repo root) and this plan. Where they disagree, this plan wins; report the disagreement in the phase log.
- A phase is **done** only when `.\scripts\ws.ps1 scripts/gate.sh <N>` prints `GATE <N>: PASS` *and* the browser checks pass *and* `docs/phase-logs/phase-<N>.md` exists with the required sections. Nothing else counts.

---

## Global Constraints

- OS: Windows 11 host. All C/C++ builds, Python, tests and sanitizers run **inside WSL2 Ubuntu 24.04**. Never build C++ on Windows. TSan and rr do not exist on Windows.
- Repo root (Windows): `C:\Users\Profile 1\ByteAskEval`. Repo root (WSL): `/mnt/c/Users/Profile 1/ByteAskEval`, symlinked as `~/proofsmith`.
- Work root (WSL, Linux filesystem, **no spaces**): `~/psw`. All C/C++ sources being built, all build dirs, all sandboxes, all clones live under `~/psw`. Sanitizer frame parsing assumes **paths without spaces**; never build from `/mnt/c/...`.
- Python venv: `~/.venvs/proofsmith` (Linux filesystem). Python 3.12. Package installed editable from `~/proofsmith`.
- Compiler: `clang`/`clang++` 18 only. C++17 minimum. No GCC builds for evaluated artifacts.
- Base flags (all variants): `-g -O1 -fno-omit-frame-pointer`.
- Variant `asan_ubsan`: add `-fsanitize=address,undefined -fno-sanitize-recover=undefined` (compile and link).
- Variant `tsan`: add `-fsanitize=thread` (compile and link). ASan and TSan are **never** combined.
- Variant `coverage`: `-g -O0 -fprofile-instr-generate -fcoverage-mapping` (alignment only).
- Variant `plain`: base flags only.
- Runtime env `asan_ubsan`: `ASAN_OPTIONS=halt_on_error=1:abort_on_error=0:detect_leaks=0:exitcode=23:symbolize=1:allocator_may_return_null=1`, `UBSAN_OPTIONS=halt_on_error=1:print_stacktrace=1:exitcode=24:symbolize=1`, `ASAN_SYMBOLIZER_PATH=/usr/bin/llvm-symbolizer`.
- Runtime env `tsan`: `TSAN_OPTIONS=halt_on_error=1:exitcode=66:second_deadlock_stack=1:symbolize=1:external_symbolizer_path=/usr/bin/llvm-symbolizer`.
- Constants: `RUNTIME_N=10`, `RUNTIME_K=8`, `EVAL_N=20`, `EVAL_BUGGY_K=16`, `EVAL_FIXED_MAX_FAILS=0`, `RUN_TIMEOUT_S=60`, `SIGNATURE_FRAMES=3`.
- Agent budget per (instance, system), identical for every system: `MAX_STEPS=50`, `MAX_TOTAL_TOKENS=500000`, `MAX_WALL_S=1800`.
- Models: evaluated runs use **only** `deepseek-v4-pro`. `deepseek-flash` is allowed **only** for live smoke tests of plumbing. No other provider, ever.
- API base URL: `https://api.deepseek.com`. Key: `DEEPSEEK_API_KEY` in `.env` at repo root. `.env` is gitignored and must never be printed, logged, committed or copied into `runs/`.
- Global spend cap: `PROOFSMITH_MAX_USD=4.50` (account balance on 2026-10-01 was $4.98). Every request checks the ledger first; exceeding the cap raises `BudgetExceeded` and stops the process.
- Network: agent sandboxes run every command under `unshare -rn` (verified working on this machine: network unreachable inside, loopback available after `ip link set lo up`).
- Hidden data: fixed commits, fix diffs, bug classes and dev tests live only under `data/*/hidden/` and `cases/*/hidden/`. These paths are never copied into a sandbox and never appear in any prompt.
- Static site: generated into `site/` by `proofsmith report build`; served by `scripts/serve.sh` at `http://localhost:8765/`. No JS frameworks, no CDN, no external fonts. Plain HTML + one CSS file + optional vanilla JS under 200 lines.
- Every number rendered in HTML carries `data-source="<results-json-relpath>#<json-pointer>"`. The browser gate cross-checks each against the JSON file.
- Line endings: LF for `*.sh *.py *.cpp *.h *.hpp *.json *.md *.txt *.patch *.cmake CMakeLists.txt` (enforced by `.gitattributes`).
- Out of scope locally: rr (WSL2 exposes no CPU PMU: `/sys/bus/event_source/devices` has no `cpu`). Never attempt to install or run rr.

---

## Executor Rules (derived from Grok 4.7's measured profile)

Grok 4.7 (xhigh) is strong at long-horizon, repo-scale implementation (DeepSWE v1.1 71–73%), has improved self-verification and a 500K context. It is measurably weaker at terminal-driven work (Terminal-Bench 4.0: 25.8% on a standard harness), produces artifacts that "validate cleanly and still need a human to check they run", hallucinates on ~29% of factual questions (AA-Omniscience), did not improve presentation quality, and regressed slightly on long-context reasoning (AA-LCR −3.7). Sources: Artificial Analysis "Benchmarking Grok 4.7"; ComputingForGeeks "Grok 4.7 Tested"; capitalandcompute "Grok 4.7 Benchmarks: One Model, Three Scores"; xAI model card. The rules below exist to neutralize those weaknesses. They are not optional.

1. **Phases are large and coherent on purpose.** Each phase is one subsystem you can hold in context. Implement the whole phase, then run the gate. Do not stop to ask for permission between steps of a phase.
2. **Terminal discipline.** From PowerShell, call WSL **only** through `.\scripts\ws.ps1 <script-relative-path> [args...]`. Never write `$` inside a PowerShell double-quoted string. Any logic with pipes, variables or quotes goes into a `.sh` file under `scripts/` first. (This rule exists because PowerShell silently rewrote `$?` and nested quotes during this plan's own probes.)
3. **The gate is the judge, not your reading of logs.** Never declare success from scrolling output. Success = the literal line `GATE <N>: PASS` printed by `scripts/gate.sh`. If the gate fails, fix the code, not the gate.
4. **Real execution beats validation.** Every gate includes real compiled binaries producing real sanitizer output. Never mock sanitizer output except via fixtures captured from real runs in Phase 0. Never hardcode an expected result into production code.
5. **Do not edit tests to make them pass.** If a test in this plan is genuinely wrong (for example, TSan behaves differently than the plan assumes), keep the test, mark it `xfail(strict=True, reason=...)` with the observed evidence, and record it under "Deviations" in the phase log. The orchestrator decides.
6. **No invented facts.** Any claim about ByteAsk must come from `docs/claims.md` (URL + verbatim quote + fetch date). Any dataset fact (issue text, commit sha, URL) must be fetched, never recalled. Any number in a page or README must come from a results JSON. If you don't know, write `UNKNOWN` and log it.
7. **No case-specific tuning.** Prompts and pipeline code must never mention a specific instance, function name, file name or repo from any dataset. Gates include a grep that fails the phase if they do.
8. **Presentation needs a second look.** After the browser gate passes, take the listed screenshots, look at them, and fix anything that looks broken or cramped before writing the phase log. The orchestrator reviews the screenshots too.
9. **Spend discipline.** Before any live DeepSeek call, run `proofsmith ledger status` and write the remaining budget in the phase log. Respect each phase's spend ceiling. If a phase would exceed its ceiling, stop and report.
10. **Stop at the gate.** When the gate passes, write the phase log, commit, tag `phase-<N>-done`, and stop. Do not start the next phase.
11. **Push back with evidence.** If the plan is wrong, say so in the phase log with the command and output that proves it. Do not quietly bend the implementation to match a wrong plan, and do not quietly bend the plan to match a wrong implementation.

### Phase log format (`docs/phase-logs/phase-<N>.md`)

```markdown
# Phase <N> log
## Result
GATE <N>: PASS   (paste the final 30 lines of gate output verbatim)
## What was built
- <file>: <one line>
## Browser checks
- <check id>: PASS/FAIL, what was observed
- Screenshots: docs/evidence/phase-<N>/<name>.png (list)
## Spend
- Ledger before: $X.XX  after: $Y.YY  phase ceiling: $Z.ZZ
## Deviations from plan
- <none> or each deviation with evidence
## Open issues for the orchestrator
- <none> or list
```

### Browser checks: two layers, both required

- **Layer A, automated (authoritative):** `.\scripts\ws.ps1 scripts/browser_gate.sh <N>` runs `scripts/browser_gate.py --phase <N>` with Playwright (Chromium, headless) against `http://localhost:8765/`. It fails on: any listed check failing, any console error, any failed network request, horizontal overflow at 1280×800 or 390×844, any `data-source` value mismatch. It saves screenshots to `docs/evidence/phase-<N>/`. `scripts/gate.sh <N>` calls it.
- **Layer B, interactive (browser control):** If you have a browser-control tool (for example Cursor's built-in browser), open the listed URLs, perform the listed interactions, and record what you saw in the phase log. If you do not have one, write "Layer B: no browser tool available" and the orchestrator performs Layer B.

---

## Contracts (single source of truth; Phase 0 copies this section to `docs/interfaces.md`)

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

---

## Phase map

| Phase | Name | LLM spend ceiling | Depends on |
|---|---|---|---|
| 0 | Foundation, toolchain doctor, gate and browser infrastructure | $0 | — |
| 1 | Oracle core and the `orderd` deadlock demo (deterministic, no LLM) | $0 | 0 |
| 2 | DeepSeek client, spend ledger, sandbox, agent loop, run viewer | $0.10 | 0 |
| 3 | Proofsmith pipeline: issue → oracle → harness → accept/abstain → freeze | $0.75 | 1, 2 |
| 4 | Track B curation: real lifetime and concurrency bugs that build under sanitizers | $0 | 1 |
| 5 | Baselines B0/B1, hidden evaluator, alignment, Track A ingestion | $0.75 | 3, 4 |
| 6 | Full evaluation run, metrics, kill criteria (**requires user approval of budget**) | rest of cap | 5 |
| 7 | Write-up, worked cases, send-ready package, one-command reproduction | $0 | 6 |
| 8 | Gate experiment (only if the Track B kill criterion passed) | user-approved | 7 |
| 9 | ByteAsk integration (MCP server + `byteask exec` wrapper) and benchmark release | $0 | 7 |

Phases 0–7 produce the thing you send. Phases 8–9 are the doc's weeks 2–4 and run only if the numbers justify them.

**Why this shape:** the deterministic machinery (Phase 1) is built and proven before any model touches it, so later failures can be blamed on the model rather than the plumbing. The demo, which is the moment that makes ByteAsk say "this guy is nuts", exists by the end of Phase 1 with zero API spend. Dataset curation (Phase 4) is the riskiest step and only depends on Phase 1, so the orchestrator may run it in parallel with Phases 2–3 if two executors are available.

---

## Phase 0 — Foundation, toolchain doctor, gate and browser infrastructure

**Why it matters:** every later phase is judged by `gate.sh` and `browser_gate.py`. If those are weak, everything after is unverified. This phase also captures the **real** sanitizer outputs that every parser test depends on.

**Already true on this machine (verified 2026-10-01):** WSL2 Ubuntu 24.04 with 12 cores and ~7 GB RAM; clang 18.1.3; CMake 3.28.3; Ninja; llvm-symbolizer, llvm-cov, llvm-profdata, llvm-cxxfilt in `/usr/bin`; python3 3.12; `unshare -rn` blocks network; `docker` is reachable but **not needed**; `gh` is missing; disk has 950 GB free. `scratch/` holds three probe files from planning; move what you need, then delete `scratch/`.

**Files:**
- Create: `.gitattributes`, `.gitignore` (extend the existing one), `pyproject.toml`, `scripts/ws.ps1`, `scripts/setup_wsl.sh`, `scripts/setup_root.sh`, `scripts/gate.sh`, `scripts/check_no_tuning.sh`, `scripts/browser_gate.sh`, `scripts/browser_gate.py`, `scripts/serve.sh`
- Create: `proofsmith/__init__.py`, `proofsmith/config.py`, `proofsmith/cli.py`, `proofsmith/toolchain.py`, `proofsmith/runtime/proofsmith_check.h`, `proofsmith/oracles/variants.py`, `proofsmith/report/site.py`, `proofsmith/report/templates/base.html.j2`, `proofsmith/report/templates/index.html.j2`, `proofsmith/report/static/site.css`
- Create: `tests/probes/{heap_overflow,use_after_free,signed_overflow,data_race,lock_order,check_fail}.cpp`, `tests/fixtures/sanitizer/*.txt` (generated), `tests/phase0/test_config.py`, `tests/phase0/test_toolchain.py`, `tests/phase0/test_site.py`
- Create: `docs/interfaces.md` (copy of the Contracts section), `docs/claims.md`, `docs/phase-logs/phase-0.md`

**Interfaces:**
- Produces: `proofsmith.config` constants (names exactly as in Global Constraints); `VARIANTS: dict[str, Variant]` with `Variant(name:str, cxxflags:str, ldflags:str, env:dict[str,str])`; `toolchain.doctor() -> list[ProbeResult]` with `ProbeResult(name, variant, expected_kind, observed_kind, ok:bool, output_path:str)`; CLI `proofsmith doctor` writes `results/toolchain.json`; `proofsmith report build` writes `site/`.

- [ ] **Step 1: Git and line endings.** Run `git init` in the repo root if `.git` is missing. Write `.gitattributes`:

```
* text=auto
*.sh text eol=lf
*.py text eol=lf
*.cpp text eol=lf
*.h text eol=lf
*.hpp text eol=lf
*.json text eol=lf
*.md text eol=lf
*.txt text eol=lf
*.patch text eol=lf
*.cmake text eol=lf
CMakeLists.txt text eol=lf
*.ps1 text eol=crlf
*.png binary
```

Append to `.gitignore`: `runs/`, `site/`, `__pycache__/`, `*.egg-info/`, `.pytest_cache/`, `scratch/`.

- [ ] **Step 2: The PowerShell bridge.** `scripts/ws.ps1`:

```powershell
param([Parameter(Mandatory=$true)][string]$Script, [Parameter(ValueFromRemainingArguments=$true)][string[]]$Rest)
$ErrorActionPreference = 'Stop'
$argList = @('-e', 'bash', '-lc', 'cd ~/proofsmith && source ~/.venvs/proofsmith/bin/activate 2>/dev/null; bash "$0" "$@"', $Script) + $Rest
& wsl.exe @argList
exit $LASTEXITCODE
```

The single-quoted bash string is passed literally; `$0`/`$@` are expanded by bash, not PowerShell. Verified during planning on PowerShell 7.6.6: an argument with spaces arrives intact, a literal `$HOME` arrives unexpanded, and the script's exit code propagates to `$LASTEXITCODE`.

- [ ] **Step 3: WSL setup scripts.** `scripts/setup_root.sh` (run once as `wsl -u root -e bash /mnt/c/Users/Profile\ 1/ByteAskEval/scripts/setup_root.sh`):

```bash
#!/usr/bin/env bash
set -euo pipefail
export DEBIAN_FRONTEND=noninteractive
apt-get update -qq
apt-get install -y -qq universal-ctags gh iproute2 curl jq
/home/*/.venvs/proofsmith/bin/python -m playwright install-deps chromium || true
echo "setup_root: OK"
```

`scripts/setup_wsl.sh` (run as the normal user via `wsl -e bash "/mnt/c/Users/Profile 1/ByteAskEval/scripts/setup_wsl.sh"`):

```bash
#!/usr/bin/env bash
set -euo pipefail
ln -sfn "/mnt/c/Users/Profile 1/ByteAskEval" "$HOME/proofsmith"
mkdir -p "$HOME/psw"
python3 -m venv "$HOME/.venvs/proofsmith"
source "$HOME/.venvs/proofsmith/bin/activate"
pip install -q --upgrade pip
pip install -q -e "$HOME/proofsmith[dev]"
python -m playwright install chromium
echo "setup_wsl: OK"
```

Run order: `setup_wsl.sh` → `setup_root.sh` (it installs Playwright's system deps using the venv) → `setup_wsl.sh` again (idempotent).

- [ ] **Step 4: `pyproject.toml`.** Package `proofsmith`, `requires-python = ">=3.12"`, dependencies `openai>=1.40`, `pydantic>=2.7`, `jinja2>=3.1`, `python-dotenv>=1.0`, `jsonschema>=4.21`; extras `dev = ["pytest>=8", "pytest-timeout>=2.3", "playwright>=1.45"]`; script `proofsmith = "proofsmith.cli:main"`; pytest markers `live` ("calls the DeepSeek API") and `slow` ("builds real C++").

- [ ] **Step 5: `proofsmith/config.py`.** All constants from Global Constraints with exactly those names, plus `REPO = Path(__file__).resolve().parents[1]`, `WORK = Path.home() / "psw"`, `SITE = REPO / "site"`, `RESULTS = REPO / "results"`, `RUNS = REPO / "runs"`, `EVAL_MODEL = "deepseek-v4-pro"`, `DEV_MODEL = "deepseek-flash"`, `API_BASE = "https://api.deepseek.com"`, `MAX_USD = float(os.environ.get("PROOFSMITH_MAX_USD", "4.50"))`. Load `.env` with python-dotenv without printing it.

- [ ] **Step 6: `proofsmith/oracles/variants.py`.** Exactly four variants, flags and env verbatim from Global Constraints. `ldflags` for sanitizer variants repeat the `-fsanitize=...` flag. The coverage variant's env is `LLVM_PROFILE_FILE=<set at runtime>`.

- [ ] **Step 7: `proofsmith/runtime/proofsmith_check.h`:**

```cpp
#pragma once
#include <cstdio>
#include <cstdlib>

#define PS_CHECK(cond)                                                              \
  do {                                                                              \
    if (!(cond)) {                                                                  \
      std::fprintf(stderr, "PROOFSMITH_CHECK_FAILED %s:%d: %s\n", __FILE__, __LINE__, #cond); \
      std::fflush(stderr);                                                          \
      std::abort();                                                                 \
    }                                                                               \
  } while (0)
```

- [ ] **Step 8: Probes.** Six tiny programs in `tests/probes/`: `heap_overflow.cpp` (write one past a `new int[8]`), `use_after_free.cpp` (read after `delete`), `signed_overflow.cpp` (`INT_MAX + v` with `v` read from `argc`), `data_race.cpp` (two `std::thread`s incrementing a plain `int` 10000 times each), `lock_order.cpp` (thread 1 locks A then B and is joined; thread 2 then locks B then A — the same shape as `scratch/tsan_smoke.cpp`), `check_fail.cpp` (includes `proofsmith_check.h`, `PS_CHECK(1 + 1 == 3)`). `toolchain.doctor()` copies them to `~/psw/probes/`, compiles each with its variant (`asan_ubsan` for the first three, `tsan` for the next two, `plain` for the last), runs each with the variant env, and writes the combined stdout+stderr to `tests/fixtures/sanitizer/<name>.txt`. Expected kinds: `asan:heap-buffer-overflow`, `asan:heap-use-after-free`, `ubsan:signed-integer-overflow`, `tsan:data-race`, `tsan:lock-order-inversion`, `assert`. In this phase, `observed_kind` uses a minimal regex. Phase 1 replaces it with `parse_evidence`.

- [ ] **Step 9: Gate and browser infrastructure.**

`scripts/gate.sh`:

```bash
#!/usr/bin/env bash
set -uo pipefail
N="${1:?phase number}"
cd ~/proofsmith
source ~/.venvs/proofsmith/bin/activate
fail=0
echo "== pytest tests/phase0..phase${N}"
dirs=""; for i in $(seq 0 "$N"); do [ -d "tests/phase$i" ] && dirs="$dirs tests/phase$i"; done
pytest -q $dirs -m "not live" || fail=1
if [ -f "scripts/gate_phase${N}.sh" ]; then echo "== phase-specific checks"; bash "scripts/gate_phase${N}.sh" || fail=1; fi
echo "== no case-specific prompt tuning"
bash scripts/check_no_tuning.sh || fail=1
echo "== browser gate"
bash scripts/browser_gate.sh "$N" || fail=1
if [ "$fail" -eq 0 ]; then echo "GATE ${N}: PASS"; else echo "GATE ${N}: FAIL"; exit 1; fi
```

Every gate re-runs all earlier phases' offline tests, so regressions are caught. `scripts/check_no_tuning.sh` greps `proofsmith/prompts/` and `proofsmith/pipeline.py` for every instance id, every `fix_files` entry, and every function name listed in hidden JSONs. It exits 1 on any hit. Before any dataset exists it passes trivially.

`scripts/serve.sh` (re)starts `python -m http.server 8765 --directory site` in the background, writes the PID to `runs/serve.pid`, waits until `curl -s localhost:8765/` returns 200, and prints `serve: OK`. `scripts/browser_gate.sh N` runs `proofsmith report build`, then `serve.sh`, then `python scripts/browser_gate.py --phase N`.

`scripts/browser_gate.py`: Playwright sync API, Chromium headless. Structure: `CHECKS: dict[int, list[Callable[[Page], None]]]`; each check raises `AssertionError` with a clear message. Global per-page assertions: zero `console` messages of type `error`; zero `requestfailed` events; at widths 1280 and 390, `document.documentElement.scrollWidth <= window.innerWidth`; every element with `data-source` has text equal to the value at that JSON pointer (formatted with `format_number` from `proofsmith/report/site.py`). Screenshots: `docs/evidence/phase-<N>/<check>-<width>.png`. Print `BROWSER <N>: PASS` or the failures.

- [ ] **Step 10: Site skeleton.** `report/site.py: build_site()` renders `index.html` from `results/toolchain.json`. Base template: header "Proofsmith", nav (Toolchain, Demo, Runs, Track B, Results; links to pages that don't exist yet are hidden), footer with the git short sha. CSS: system font stack, max-width 1100px, a 16px base, a monospace block style for raw reports, status pills (`.pill-pass` green, `.pill-fail` red, `.pill-warn` amber, `.pill-info` grey), and tables with sticky headers. Every interactive or checked element gets a `data-testid`.

- [ ] **Step 11: `docs/claims.md`.** Seed it with exactly these verified entries (fetched 2026-10-01) and these unverified ones:

```markdown
# Claims ledger. Only entries marked VERIFIED may be stated in any output.

## C1 VERIFIED — homepage headline
URL: https://byteask.ai/ (fetched 2026-10-01)
Quote: "Writes C++. Proves it compiles, runs, and passes."

## C2 VERIFIED — homepage gdb demo is an order-book deadlock fixed with scoped_lock
URL: https://byteask.ai/ (fetched 2026-10-01)
Quote: "my gdb is stopped on the deadlock in orderd, take a look" / "#3 OrderBook::cancel (...) at order_book.cpp:214" / "p risk_mtx_._M_mutex.__data.__owner ... (held by the risk thread)" / "+ std::scoped_lock lk(book_mtx_, risk_mtx_);"

## C3 VERIFIED — homepage Evidence section shows tests passing on a tree with an ASan bug
URL: https://byteask.ai/ (fetched 2026-10-01)
Quote: "AddressSanitizer: heap-buffer-overflow ... in OrderBook::cancel_all()" and "ctest on the same tree, same run." with "100% tests passed, 0 tests failed out of 3" (book_ops, risk_engine, wire_codec)

## C4 VERIFIED — ByteAsk connects MCP servers
URL: https://docs.byteask.ai/docs/overview (fetched 2026-10-01)
Quote: "MCP servers | Connect any Model Context Protocol server"

## C5 VERIFIED — headless mode
URL: https://docs.byteask.ai/docs/overview (fetched 2026-10-01)
Quote: "Non-interactive mode | Scripting-friendly `exec` subcommand with JSONL output"

## C6 VERIFIED — built-in sanitizer and rr tools
URL: https://docs.byteask.ai/docs/features (fetched 2026-10-01)
Quote: "`cpp_sanitize` | Build and run with ASan, UBSan, TSan, or Valgrind" and "`debug_record` | Record and replay a deterministic trace with rr"

## U1 UNVERIFIED — hiring page: patch correctness is an open problem; "knowing when the honest answer is 'we don't know'"
## U2 UNVERIFIED — CEO rule: "use AI to write the deterministic tool"
## U3 UNVERIFIED — CTO owns harness, benchmarks and model training
## U4 UNVERIFIED — Multi-SWT-Bench figures (126 C++ instances, 52.5%, ~994K LoC)
```

- [ ] **Step 12: Tests.**
  - `tests/phase0/test_config.py`: asserts each constant's exact value; asserts `VARIANTS` keys are `{"plain","asan_ubsan","tsan","coverage"}`; asserts `"address" in VARIANTS["asan_ubsan"].cxxflags and "thread" not in it`; asserts `"thread" in VARIANTS["tsan"].cxxflags and "address" not in it`; asserts `.env` is listed in `.gitignore`.
  - `tests/phase0/test_toolchain.py` (marker `slow`, but included in the gate): runs `doctor()`; asserts all six `ok`; asserts each fixture file exists, is over 200 bytes, and contains `ERROR: AddressSanitizer`, `runtime error:`, `WARNING: ThreadSanitizer` or `PROOFSMITH_CHECK_FAILED` as appropriate; asserts the lock-order fixture contains `lock-order-inversion`; asserts the probe binaries' sources were built from `~/psw` (the fixture text contains `/psw/probes/` and no `/mnt/c/`).
  - `tests/phase0/test_site.py`: `build_site()` creates `site/index.html` and `site/site.css`; the HTML contains `data-testid="toolchain-table"`.

- [ ] **Step 13: Gate.** `.\scripts\ws.ps1 scripts/gate.sh 0` → `GATE 0: PASS`.

**Browser checks (phase 0):**
- `B0.1` `/` loads; the title contains "Proofsmith".
- `B0.2` `[data-testid=toolchain-table]` has exactly 6 rows; every row shows `.pill-pass`; each row's observed kind equals its expected kind.
- `B0.3` `[data-testid=clang-version]` text contains `clang version 18`. Its `data-source` points to `results/toolchain.json#/clang_version`.
- `B0.4` Each row has a "raw output" `<details>`. Opening the lock-order row shows text containing `lock-order-inversion`.
- Screenshots: `index-1280.png`, `index-390.png`.
- Layer B: open `/`, expand two raw outputs, confirm they're readable (monospace, wrapped, no overflow).

**Done when:** the gate passes, `docs/phase-logs/phase-0.md` is complete, and the work is committed and tagged `phase-0-done`.

---

## Phase 1 — Oracle core and the `orderd` deadlock demo (deterministic, no LLM)

**Why it matters:** this is the "holy shit" artifact. ByteAsk's own homepage shows an order-book deadlock in `orderd`, found by attaching gdb to a process that had already hung, and fixed with `std::scoped_lock lk(book_mtx_, risk_mtx_)` (claims C2). Their Evidence section shows `ctest` at 100% on a tree with a real ASan bug (claims C3). Phase 1 shows a frozen TSan check that fails on that deadlock **without the program ever hanging**, rejects a plausible timing-only "fix" that passes every existing test, and accepts ByteAsk's exact fix. Planning probes already confirmed the core behavior on this machine with clang 18: buggy → `lock-order-inversion`, exit 66; sleep-only patch → still reported, exit 66; `scoped_lock` in `cancel` only → no report, exit 0; consistent order → no report, exit 0.

The harness in this phase is **hand-written** (system `reference`) and labeled as such on the page. Phase 3 replaces it with a Proofsmith-generated one.

**Files:**
- Create: `cases/orderd/instance.json`, `cases/orderd/buggy/{CMakeLists.txt,order_book.h,order_book.cpp,wire_codec.h,wire_codec.cpp,tests/book_ops.cpp,tests/risk_engine.cpp,tests/wire_codec.cpp}`
- Create: `cases/orderd/hidden/hidden.json`, `cases/orderd/hidden/fix.patch` (ByteAsk's fix), `cases/orderd/variants/{timing_backoff,scoped_cancel,consistent_order}.patch`, `cases/orderd/stress/stress.cpp`, `cases/orderd/reference_harness/{harness.cpp,build.sh}`
- Create: `proofsmith/oracles/signature.py`, `proofsmith/oracles/runner.py`, `proofsmith/oracles/acceptance.py`, `proofsmith/oracles/builds.py`, `proofsmith/harness.py`, `proofsmith/freeze.py`, `proofsmith/datasets/schema.py`, `proofsmith/demo.py`, `proofsmith/report/templates/demo.html.j2`
- Create: `scripts/gate_phase1.sh`, `tests/phase1/{test_signature.py,test_acceptance.py,test_freeze.py,test_builds.py,test_demo_orderd.py}`
- Modify: `proofsmith/toolchain.py` (use `parse_evidence`), `proofsmith/cli.py` (`proofsmith demo orderd`)

**Interfaces:**
- Consumes: `config` constants; `VARIANTS`; fixtures `tests/fixtures/sanitizer/*.txt`.
- Produces:
  - `parse_evidence(output:str, exit_code:int, timed_out:bool, repo_root:str) -> Evidence`
  - `normalize_function(name:str) -> str`
  - `run_n(binary:Path, variant:str, n:int, timeout_s:int, cwd:Path, repo_root:str, log_dir:Path) -> list[RunResult]` with `RunResult(index:int, exit_code:int, timed_out:bool, duration_s:float, evidence:Evidence, output_path:str)`
  - `decide(runs:list[RunResult], k:int, oracle:str) -> Decision` with `Decision(accepted:bool, signature:str|None, count:int, n:int, reason:str)`
  - `BuildRecipe` / `Instance` / `HiddenInstance` (pydantic, mirroring the Contracts JSON)
  - `materialize(instance:Instance, dest:Path) -> Path` (copy a dir source or clone+checkout a git source into `dest`; returns the repo root)
  - `apply_patch(repo:Path, patch:Path) -> None` (`git apply` or `patch -p1`, raising on failure)
  - `build_variant(repo:Path, variant:str, recipe:BuildRecipe, out_root:Path) -> BuildResult` with `BuildResult(ok:bool, build_dir:Path, compile_commands:Path|None, log_path:Path, duration_s:float)`
  - `compile_harness(repo:Path, build:BuildResult, variant:str, out_dir:Path) -> HarnessBuild` with `HarnessBuild(ok:bool, binary:Path|None, log_path:Path)`
  - `freeze(repo:Path, meta:dict, out_dir:Path) -> Path`, `load_bundle(path:Path) -> dict` (raises `TamperError`), `verify_bundle(bundle_dir:Path, repo:Path, recipe:BuildRecipe, n:int, work:Path) -> VerifyResult` with `VerifyResult(build_ok:bool, fails:int, n:int, runs:list[RunResult])`
  - `results/demo/orderd.json`

- [ ] **Step 1: The `orderd` project.** A CMake project with library `orderd_core` (`order_book.cpp`, `wire_codec.cpp`) and three test executables registered with `add_test`: `book_ops`, `risk_engine`, `wire_codec`. These names deliberately mirror ByteAsk's homepage tests. All tests are single-threaded and pass on the buggy tree. The bug is in `order_book.h/.cpp`:

```cpp
// order_book.h (core of it)
namespace orderd {
enum class Side { Buy, Sell };
struct Order { std::uint64_t id; std::string account; Side side; std::int64_t price_ticks; std::int64_t qty; };

class OrderBook {
 public:
  explicit OrderBook(std::int64_t per_account_limit);
  bool add(const Order& o);              // reserve exposure (risk_mtx_), then rest the order (book_mtx_); never nested
  bool cancel(std::uint64_t order_id);   // BUG: holds book_mtx_, then takes risk_mtx_
  std::size_t risk_sweep();              // risk thread: BUG: holds risk_mtx_, then takes book_mtx_
  std::int64_t exposure(const std::string& account) const;
  std::size_t resting() const;
 private:
  mutable std::mutex book_mtx_;
  mutable std::mutex risk_mtx_;
  std::map<std::uint64_t, Order> orders_;                    // guarded by book_mtx_
  std::unordered_map<std::string, std::int64_t> exposure_;   // guarded by risk_mtx_
  std::int64_t limit_;
};
}  // namespace orderd

// order_book.cpp (the two inverted paths)
bool OrderBook::cancel(std::uint64_t order_id) {
  std::lock_guard<std::mutex> book(book_mtx_);
  auto it = orders_.find(order_id);
  if (it == orders_.end()) return false;
  const Order o = it->second;
  orders_.erase(it);
  std::lock_guard<std::mutex> risk(risk_mtx_);
  exposure_[o.account] -= o.price_ticks * o.qty;
  return true;
}

std::size_t OrderBook::risk_sweep() {
  std::lock_guard<std::mutex> risk(risk_mtx_);
  std::lock_guard<std::mutex> book(book_mtx_);
  std::unordered_map<std::string, std::int64_t> recomputed;
  for (const auto& [id, o] : orders_) recomputed[o.account] += o.price_ticks * o.qty;
  std::size_t breaches = 0;
  for (const auto& [acct, v] : recomputed) if (v > limit_) ++breaches;
  exposure_ = std::move(recomputed);
  return breaches;
}
```

`wire_codec` encodes and decodes an `Order` to a fixed little-endian byte layout (trivial; it exists so the test list matches ByteAsk's).

- [ ] **Step 2: The issue text** (`cases/orderd/instance.json`, symptoms only; it must not mention locks, mutexes, ordering or scoped_lock):

```
title: orderd occasionally freezes under load; process must be killed
body:
A few times a week in production, orderd stops responding during busy periods.
CPU drops to ~0% and no more log lines appear; we have to kill -9 it.
The last log lines before a freeze always show a cancel being processed while the
periodic risk sweep is running. All ctest tests pass and we cannot reproduce it on
demand locally. Expected: cancels and the risk sweep can run at the same time
without the process ever freezing.
```

`mentions_fix: false`, `rewritten: false`, `url: null`.

- [ ] **Step 3: Patches.**
  - `hidden/fix.patch` (ByteAsk's fix): `cancel` uses `std::scoped_lock lk(book_mtx_, risk_mtx_);` at the top instead of two `lock_guard`s; `risk_sweep` unchanged.
  - `variants/scoped_cancel.patch`: identical to `fix.patch` (kept separately so the demo's patch list is self-describing).
  - `variants/consistent_order.patch`: `risk_sweep` takes `book_mtx_` first, then `risk_mtx_`.
  - `variants/timing_backoff.patch` (the plausible wrong fix): in `risk_sweep`, before taking `risk_mtx_`, add `std::this_thread::sleep_for(std::chrono::microseconds(200));` with the comment `// back off so the sweep doesn't collide with cancels`. Lock order unchanged.

- [ ] **Step 4: Stress repro** (`stress/stress.cpp`; this is what a "reproduce first" agent typically writes). Two threads loop `add` + `cancel` on random orders and one thread loops `risk_sweep`, for 300 ms total, then everything is joined. Built with variant `plain`. A run that does not finish within 5 s counts as a fail (timeout). The demo runs it 20 times per variant.

- [ ] **Step 5: Reference harness** (`reference_harness/harness.cpp` + `build.sh`, system `reference`). It creates an `OrderBook` and runs thread A (`add` + `cancel` of one order) to completion and joins it, then runs thread B (`risk_sweep`) to completion. It is sequential, so it can never actually deadlock. Under TSan it reports `lock-order-inversion`. `build.sh` compiles `harness.cpp` with `$PS_CXX $PS_CXXFLAGS -I"$PS_REPO" -I"$PS_INCLUDE"` and links `$PS_BUILD_DIR/liborderd_core.a` with `$PS_LDFLAGS -pthread` into `$PS_OUT/harness`.

- [ ] **Step 6: `signature.py`.** Implement the Contracts rules. Kind detection, in this precedence:
  1. `PROOFSMITH_CHECK_FAILED (\S+):(\d+):` → `assert`, with the frame from that file:line.
  2. `Assertion .+ failed` (glibc `assert`) with `(\S+):(\d+):` → `assert`.
  3. `ERROR: AddressSanitizer: ([a-z-]+)` → `asan:<g1>`.
  4. `runtime error: ([^:]+)` → `ubsan:<slug>`, where slug = lowercased, non-alphanumerics → `-`, stripped of `-`.
  5. `WARNING: ThreadSanitizer: ([^(\n]+)` → `tsan:<slug>` (so "lock-order-inversion (potential deadlock)" → `tsan:lock-order-inversion`, "data race" → `tsan:data-race`).
  6. Otherwise: `timed_out` → `timeout`; `exit_code < 0` or 128 < `exit_code` < 160 → `crash:<SIGNAME>`; nonzero → `exit:<code>`; else `none`.

  Frames: parse every line matching `^\s*#(\d+)\s+(?:0x[0-9a-fA-F]+\s+in\s+)?(.+?)\s+(/[^\s:]+):(\d+)(?::\d+)?(?:\s+\(.*\))?\s*$`, in order of appearance across all stacks. For TSan this means across all "Mutex ... acquired here" and "Previous write" blocks. `normalize_function`: strip a trailing ` const`; if `"operator()"` is in the name, cut right after the first `operator()`; else cut at the first `(`; strip leading `"(anonymous namespace)::"`; and collapse lambda ids `$_<n>` to `$_`.

- [ ] **Step 7: `acceptance.py`:**

```python
ELIGIBLE = {"tsan": ("tsan:",), "asan_ubsan": ("asan:", "ubsan:"), "assertion": ("assert",)}

def decide(runs, k, oracle):
    n = len(runs)
    prefixes = ELIGIBLE[oracle]
    counts = Counter()
    for r in runs:
        ev = r.evidence
        if not ev.kind.startswith(prefixes):
            continue
        if ev.kind != "assert" and not ev.app_frames:
            continue  # sanitizer report with no application frame = the harness is buggy, not the project
        counts[ev.signature] += 1
    if not counts:
        return Decision(False, None, 0, n, f"no eligible {oracle} evidence in {n} runs")
    sig, c = counts.most_common(1)[0]
    if c >= k:
        return Decision(True, sig, c, n, f"stable signature in {c}/{n} runs")
    return Decision(False, sig, c, n, f"modal signature only {c}/{n} (< k={k}); {len(counts)} distinct signatures")
```

- [ ] **Step 8: `builds.py`, `harness.py`, `freeze.py`.**
  - `build_variant`, for CMake: `cmake -S <repo> -B <out_root>/<variant> -G Ninja -DCMAKE_C_COMPILER=clang -DCMAKE_CXX_COMPILER=clang++ -DCMAKE_BUILD_TYPE= -DCMAKE_C_FLAGS=<cxxflags> -DCMAKE_CXX_FLAGS=<cxxflags> -DCMAKE_EXE_LINKER_FLAGS=<ldflags> -DCMAKE_SHARED_LINKER_FLAGS=<ldflags> -DCMAKE_EXPORT_COMPILE_COMMANDS=ON <recipe.cmake_args>`, then `cmake --build ... -j <recipe.jobs> [--target ...]`. For `make`: `make -j<jobs> CC=clang CXX=clang++ CFLAGS=... CXXFLAGS=... LDFLAGS=...`. For `custom`: run `recipe.custom_script` with the same `PS_*` env. Log everything to `log_path`. Builds are cached by `(tree hash, variant)` under `~/psw/cache/builds/`.
  - `compile_harness` runs `bash proofsmith_harness/build.sh` with the Contracts env and checks that `$PS_OUT/harness` is executable.
  - `freeze` copies `proofsmith_harness/` to `<out>/harness/`, writes `verifier.json` with sha256 per file, and computes `buggy_tree_sha256` over sorted (relpath, sha256) of all files outside `proofsmith_harness/` and `.git/`.
  - `load_bundle` recomputes the hashes and raises `TamperError` on any mismatch, missing file or extra file.
  - `verify_bundle` copies `harness/` into `<repo>/proofsmith_harness/`, runs `build_variant` and `compile_harness`, runs `run_n`, and counts fails per the Contracts definition.

- [ ] **Step 9: `demo.py` (`proofsmith demo orderd`).**
  - Materialize the buggy tree to `~/psw/demo/orderd/buggy`. Apply each variant patch to its own copy: `timing_backoff`, `scoped_cancel`, `consistent_order`.
  - On each of the four trees: `build_variant(plain)` then `ctest` (record pass/total); the stress repro ×20 (fails, timeouts); and the reference bundle frozen once on **buggy**, then `verify_bundle(n=20, variant=tsan)`.
  - Also record the reference harness's `decide(runs[:10], k=8, oracle="tsan")` on buggy.
  - Write `results/demo/orderd.json`:

```json
{
  "schema": "proofsmith.demo/1",
  "instance_id": "orderd-deadlock",
  "harness_source": "reference",
  "issue": {"title": "...", "body": "..."},
  "verifier": {"signature": "...", "runtime": {"n": 10, "k": 8, "fails": 10}, "files": {"...": "sha256"}},
  "rows": {
    "buggy":            {"ctest": {"passed": 3, "total": 3}, "stress": {"fails": 0, "n": 20}, "verifier": {"fails": 20, "n": 20}},
    "timing_backoff":   {"ctest": {"passed": 3, "total": 3}, "stress": {"fails": 0, "n": 20}, "verifier": {"fails": 20, "n": 20}},
    "scoped_cancel":    {"ctest": {"passed": 3, "total": 3}, "stress": {"fails": 0, "n": 20}, "verifier": {"fails": 0,  "n": 20}},
    "consistent_order": {"ctest": {"passed": 3, "total": 3}, "stress": {"fails": 0, "n": 20}, "verifier": {"fails": 0,  "n": 20}}
  },
  "raw_report_buggy": "<first TSan report text>",
  "generated_at": "..."
}
```

  The numbers above are placeholders for shape only; the real values come from the run. Stress fails are whatever happens. Report them honestly, including the case where the stress repro hangs often on buggy. The point of the page is the comparison, not a particular stress number.

- [ ] **Step 10: Demo page** (`site/demo/index.html`). Sections, in order:
  1. "The issue": the issue text, verbatim.
  2. "The frozen check": oracle `tsan`, signature, a 10-dot run strip (red = failed with signature), the sha256 of `harness.cpp`, and a label `Reference harness (hand-written)` with `data-testid="harness-source-label"`.
  3. "Who says it's fixed?": a 4×3 matrix (rows: buggy, timing backoff, ByteAsk's fix (`scoped_lock` in `cancel`), consistent lock order; columns: existing tests (ctest), stress repro ×20, Proofsmith check ×20). Each cell has `data-source` pointing into `results/demo/orderd.json`.
  4. "The evidence": a `<details>` with the raw TSan report.
  5. "Why this matters": one paragraph citing claims C2 and C3 with links, and no other claims.

- [ ] **Step 11: Tests.**
  - `test_signature.py`: for each Phase 0 fixture, `parse_evidence(...).kind` equals the expected kind. For the lock-order fixture with `repo_root` = the probe dir: at least one app frame, the signature starts with `tsan:lock-order-inversion|`, and it contains no hex addresses and no line numbers. The assert fixture gives signature `assert|check_fail.cpp:<line>`. Synthetic strings: a frame line with a lambda `main::$_3::operator()() const` normalizes to `main::$_::operator()`; frames under `/usr/include` are not app frames; frames under `<repo>/proofsmith_harness/` are not app frames; a timeout gives kind `timeout`; exit code 139 gives `crash:SIGSEGV`.
  - `test_acceptance.py` (synthetic `RunResult`s): 10/10 same tsan signature → accept; 7/10 → reject with "< k=8"; 5+3 split → reject; 10 timeouts → reject; tsan evidence with zero app frames → reject; an assertion with no app frames → accept; asan evidence under the `tsan` oracle → reject.
  - `test_freeze.py`: freezing then loading round-trips; editing one byte of `harness.cpp` → `TamperError`; adding a file → `TamperError`; `buggy_tree_sha256` is stable across two freezes of the same tree.
  - `test_builds.py` (slow): `build_variant` on `cases/orderd/buggy` for `plain`, `asan_ubsan` and `tsan` all `ok`; `compile_commands.json` exists; a second call is a cache hit (under 2 s).
  - `test_demo_orderd.py` (slow): runs `proofsmith demo orderd` and then checks:
    - ctest passes 3/3 on all four rows;
    - `verifier.fails >= 16` on `buggy` and `timing_backoff`;
    - `verifier.fails == 0` on `scoped_cancel` and `consistent_order`;
    - the reference decision is accepted;
    - the signature contains `OrderBook::cancel` or `OrderBook::risk_sweep`;
    - `raw_report_buggy` contains `lock-order-inversion`.
- [ ] **Step 12:** `scripts/gate_phase1.sh` asserts `results/demo/orderd.json` validates against a JSON Schema in `tests/phase1/demo.schema.json`. Then run the gate: `GATE 1: PASS`.

**Browser checks (phase 1):**
- `B1.1` `/demo/` loads. `[data-testid=issue-body]` text equals the instance issue body.
- `B1.2` `[data-testid=matrix]` has 4 body rows × 3 result columns; every cell's text matches its `data-source`.
- `B1.3` The `timing_backoff` row shows existing tests passing and the Proofsmith check failing (`.pill-fail`) in the same row. This is the money row; assert both pills are present.
- `B1.4` The `scoped_cancel` row shows the Proofsmith check `0/20` with `.pill-pass`.
- `B1.5` `[data-testid=run-strip]` has exactly 10 dots.
- `B1.6` Opening `[data-testid=raw-report]` shows text containing `lock-order-inversion` and `OrderBook::`.
- `B1.7` `[data-testid=harness-source-label]` text is `Reference harness (hand-written)`.
- `B1.8` Every external link on the page is `https://byteask.ai/` or `https://docs.byteask.ai/...`, and each corresponds to a VERIFIED claim id shown in a `data-claim` attribute.
- Screenshots: `demo-1280.png`, `demo-390.png`, `demo-matrix-1280.png` (element screenshot).
- Layer B: open `/demo/`, read the matrix as if you were ByteAsk's CTO, and write two sentences in the phase log on whether the page makes the point within 10 seconds. If not, fix the layout and say what you changed.

**Done when:** the gate passes, the phase log is complete, and the work is committed and tagged `phase-1-done`.

---

## Phase 2 — DeepSeek client, spend ledger, sandbox, agent loop, run viewer

**Why it matters:** B0, B1 and Proofsmith must run on **one** loop with **one** tool set and **one** budget, or the comparison is meaningless. The sandbox must make cheating impossible: there is no git history to read the fix from, no network to fetch it, and no writing outside `proofsmith_harness/`.

**Spend ceiling:** $0.10, live smoke tests only, using `deepseek-flash`.

**Files:**
- Create: `proofsmith/llm.py`, `proofsmith/ledger.py`, `proofsmith/sandbox.py`, `proofsmith/agent/__init__.py`, `proofsmith/agent/tools.py`, `proofsmith/agent/loop.py`, `config/pricing.json`, `proofsmith/report/templates/run.html.j2`, `proofsmith/report/templates/runs.html.j2`
- Create: `tests/phase2/{test_ledger.py,test_llm_fake.py,test_sandbox.py,test_tools.py,test_loop.py,test_live_smoke.py}`, `scripts/gate_phase2.sh`
- Modify: `proofsmith/cli.py` (`proofsmith ledger status`, `proofsmith agent smoke`)

**Interfaces:**
- Consumes: `config`; `build_variant`, `compile_harness`, `run_n`, `parse_evidence`, `materialize` from Phase 1.
- Produces:
  - `Usage(prompt_tokens:int, completion_tokens:int, reasoning_tokens:int, cache_hit_tokens:int)`
  - `LLMResponse(content:str|None, reasoning_content:str|None, tool_calls:list[ToolCall], usage:Usage, finish_reason:str, raw:dict)` with `ToolCall(id:str, name:str, arguments:dict)`
  - `class LLMClient: __init__(model:str, ledger:Ledger, run_id:str)` and `.chat(messages:list[dict], tools:list[dict]|None, max_tokens:int) -> LLMResponse`
  - `class FakeLLM` (same `.chat` signature, constructed with `list[LLMResponse]`, records requests)
  - `class Ledger: __init__(path:Path)` with `.record(run_id, model, usage) -> float`, `.spent_usd() -> float`, `.ensure_budget() -> None` (raises `BudgetExceeded`)
  - `class Sandbox` with `.create(src_repo:Path, run_id:str) -> Sandbox` (classmethod), `.repo: Path`, `.exec(cmd:str, timeout_s:int) -> ExecResult`, `.changed_paths() -> list[str]`, `.illegal_changes() -> list[str]`, `.destroy()`. `ExecResult(exit_code:int, output:str, timed_out:bool, duration_s:float)`
  - `class ToolSet: __init__(sandbox, recipe:BuildRecipe, work:Path)` with `.schemas() -> list[dict]` and `.dispatch(name:str, args:dict) -> str`
  - `run_agent(llm, system_prompt:str, user_prompt:str, tools:ToolSet, budget:Budget, run_dir:Path) -> AgentResult` with `Budget(max_steps:int, max_total_tokens:int, max_wall_s:int)` and `AgentResult(status:"finished"|"abstained"|"budget_exhausted"|"error", final:dict, steps:int, usage:Usage, wall_s:float, cost_usd:float)`

- [ ] **Step 1: Pricing.** Fetch DeepSeek's official pricing page and write `config/pricing.json` as `{"source_url": "...", "fetched": "YYYY-MM-DD", "currency": "USD", "models": {"deepseek-v4-pro": {"input_cache_hit_per_mtok": x, "input_cache_miss_per_mtok": y, "output_per_mtok": z}, "deepseek-flash": {...}}}`. If a model's price is not on the page, set its fields to `null` and make the ledger price unknown tokens at the **highest** listed price of any model (a conservative over-estimate). Log this in the phase log. Never guess a price.

- [ ] **Step 2: Ledger.**
  - Storage is append-only JSONL at `runs/ledger.jsonl`: `{"ts", "run_id", "model", "usage", "cost_usd"}`.
  - `ensure_budget()` raises `BudgetExceeded` if `spent_usd() >= MAX_USD`. It is called before **every** request.
  - `proofsmith ledger status` prints spent, cap and remaining. It also prints the live account balance from `GET https://api.deepseek.com/user/balance` when reachable.

- [ ] **Step 3: `LLMClient`.**
  - Use the `openai` SDK with `base_url=API_BASE` and `api_key` from env. Retry 429 and 5xx with exponential backoff (1, 2, 4, 8, 16 s; max 5 tries).
  - Parse `reasoning_content` when present. When sending the conversation back, keep assistant `content` and `tool_calls` but do **not** resend `reasoning_content`, unless the live round-trip test below proves the API requires it. Record which rule applies in the phase log.
  - Never log the API key. Request and response bodies are logged to the trajectory with the `Authorization` header absent.

- [ ] **Step 4: Sandbox.**
  - `create` copies the source tree (excluding `.git`) to `~/psw/sandboxes/<run_id>/repo`, runs `git init -q && git add -A && git commit -qm snapshot` (one commit, so `git log` shows nothing useful), and creates an empty `proofsmith_harness/`.
  - `exec` writes the command to a temp script and runs `unshare -rn bash -c 'ip link set lo up 2>/dev/null; cd <repo> && bash <script>'` with the timeout. Output is merged stdout+stderr, truncated to the first 8,000 and last 12,000 characters with a `[... N chars truncated ...]` marker.
  - `changed_paths` comes from `git status --porcelain` (with untracked files). `illegal_changes` returns entries not under `proofsmith_harness/`, ignoring build dirs that live outside the repo.

- [ ] **Step 5: ToolSet.** These seven tools, with these exact names and the same descriptions for every system:
  - `run_shell(cmd: str, timeout_s: int = 120)` → exit code + truncated output, run via `Sandbox.exec`.
  - `read_file(path: str, start_line: int = 1, end_line: int = 400)` → numbered lines; only paths inside the sandbox repo.
  - `write_file(path: str, content: str)` → only paths under `proofsmith_harness/`; anything else returns an error string telling the agent the rule.
  - `list_dir(path: str = ".")`.
  - `build_variant(variant: "plain"|"asan_ubsan"|"tsan")` → ok flag, build dir, the last 60 log lines, and the `compile_commands.json` path.
  - `run_harness(variant: "plain"|"asan_ubsan"|"tsan", n: int = 1)` → compiles the harness via `compile_harness`, runs it `min(n, 10)` times, and returns per-run exit code, timed_out, `evidence.kind`, `evidence.signature`, and the first 60 lines of the first failing run's output.
  - `finish(variant: "plain"|"asan_ubsan"|"tsan", summary: str)` / `abstain(reason: str)`: terminal tools.

- [ ] **Step 6: Loop.** A standard tool-calling loop: system + user message → `chat` → execute tool calls in order → append tool results → repeat until a terminal tool is called or the budget is hit. Budget counts steps (one per model call), `prompt_tokens + completion_tokens` summed across calls, and wall clock. When a budget is hit, the result is `budget_exhausted`, with whatever is in `proofsmith_harness/` preserved. If the model replies with no tool call, append the user message `"Use a tool. Call finish(...) or abstain(...) when done."`, at most 3 times in a row, then `error`. Every event goes to `runs/<run_id>/trajectory.jsonl` as `{"t": iso, "step": int, "type": "llm_request|llm_response|tool_call|tool_result|budget|final", ...}`, plus `runs/<run_id>/summary.json`.

- [ ] **Step 7: Run viewer.** `site/runs/index.html` lists all runs (run id, system, instance, status, steps, tokens, cost, wall). `site/runs/<run_id>/index.html` shows each step: the model's text, the tool call name and arguments, and tool output in a collapsible monospace block. A budget bar shows tokens used against `MAX_TOTAL_TOKENS`. Totals have `data-source` pointing to `runs/<run_id>/summary.json`. Copy each `summary.json` into `site/data/runs/<run_id>.json` during the site build, so the data-source check can read it.

- [ ] **Step 8: Tests.**
  - `test_ledger.py`: costs are computed from `pricing.json` for known usage (exact float to 1e-9); `ensure_budget` raises at cap (set `MAX_USD` via monkeypatch); unknown-price models use the max price.
  - `test_llm_fake.py`: `FakeLLM` returns scripted responses and records requests; no network is touched (monkeypatch `socket.socket` to raise).
  - `test_sandbox.py` (slow): the snapshot has exactly 1 commit; no `.git` from the source; `exec("curl -sS -m 5 https://example.com")` fails with nonzero exit; `exec("python3 -c 'import socket; s=socket.socket(); s.bind((\"127.0.0.1\",0)); print(\"lo ok\")'")` prints `lo ok`; writing `order_book.cpp` via `exec` shows up in `illegal_changes()`; writing `proofsmith_harness/x.cpp` does not; a timeout gives `timed_out=True`.
  - `test_tools.py` (slow): `write_file("order_book.cpp", ...)` returns an error and the file is unchanged; `build_variant("tsan")` succeeds on the orderd sandbox; with the reference harness copied in, `run_harness("tsan", 2)` reports kind `tsan:lock-order-inversion` both times.
  - `test_loop.py` (FakeLLM):
    - a scripted 3-step run ending in `finish` gives `finished`;
    - step cap: 50 non-terminal calls give `budget_exhausted` at step 50;
    - token cap: a scripted usage over 500k gives `budget_exhausted`;
    - no-tool-call nudges: 3 then `error`;
    - the trajectory JSONL has one `final` event;
    - the API key string never appears in the trajectory (grep for the first 8 chars of the real key).
  - `test_live_smoke.py` (marker `live`, run explicitly by `gate_phase2.sh`): uses `deepseek-flash` on an orderd sandbox with the task "Use list_dir and read_file to find the names of the two mutex members of OrderBook, then call finish(variant='plain', summary=<the two names>)". Asserts `finished`, both `book_mtx_` and `risk_mtx_` in the summary, at least one multi-turn tool round-trip, a ledger cost over 0, and a total cost under $0.02.
- [ ] **Step 9:** `scripts/gate_phase2.sh` runs `pytest -q tests/phase2/test_live_smoke.py -m live` once and `proofsmith ledger status`. Run the gate: `GATE 2: PASS`.

**Browser checks (phase 2):**
- `B2.1` `/runs/` lists the live smoke run with status `finished`.
- `B2.2` The run page shows at least 2 steps; each tool call shows its name and arguments; at least one output block expands.
- `B2.3` The token and cost totals match `summary.json` (data-source).
- `B2.4` The budget bar's `aria-valuenow` equals total tokens and `aria-valuemax` equals 500000.
- `B2.5` The page source contains no string starting with `sk-`.
- Screenshots: `runs-1280.png`, `run-1280.png`, `run-390.png`.
- Layer B: open the run page and confirm you can follow what the agent did without reading JSON.

**Done when:** the gate passes, spend is at or under $0.10 (logged), the phase log is complete, and the work is committed and tagged `phase-2-done`.

---

## Phase 3 — Proofsmith pipeline: issue → oracle → harness → accept/abstain → freeze

**Why it matters:** this is the product. The model proposes. Deterministic code decides. If Proofsmith can't build a stable, toolchain-backed failing check, it says `NO VERIFIER: <reason>` instead of shipping a weak one.

**Spend ceiling:** $0.75, all on `deepseek-v4-pro`.

**Files:**
- Create: `proofsmith/pipeline.py`, `proofsmith/prompts/{proofsmith_system.md,classify.md,oracle_tsan.md,oracle_asan_ubsan.md,oracle_assertion.md,retry_feedback.md,harness_contract.md}`
- Create micro cases: `cases/uaf-lru/`, `cases/race-stats/`, `cases/ub-notional/`, `cases/rounding-ticks/`, `cases/vague-perf/` (each with `instance.json`, `buggy/`, `hidden/hidden.json`, `hidden/fix.patch` (none for vague-perf))
- Create: `proofsmith/report/templates/verifier.html.j2`, `tests/phase3/{test_pipeline_fake.py,test_classify.py,test_micro_cases_build.py,test_live_pipeline.py}`, `scripts/gate_phase3.sh`
- Modify: `proofsmith/demo.py` (when `results/verifiers/orderd-deadlock/proofsmith.json` exists, use that bundle as the demo's verifier and set `harness_source: "proofsmith"`), `proofsmith/cli.py` (`proofsmith make-verifier --instance <path> --out <dir>`)

**Interfaces:**
- Consumes: everything from Phases 1–2 (exact names: `materialize`, `build_variant`, `compile_harness`, `run_n`, `decide`, `freeze`, `verify_bundle`, `LLMClient`, `Ledger`, `Sandbox`, `ToolSet`, `run_agent`, `Budget`).
- Produces: `make_verifier(instance:Instance, llm:LLMClient, budget:Budget, out_dir:Path) -> VerifierResult` with `VerifierResult(status:"accepted"|"abstained"|"skipped", bundle_dir:Path|None, oracle:str|None, signature:str|None, reason:str, attempts:list[dict], usage:Usage, cost_usd:float, wall_s:float)`; `classify(issue:dict, repo_summary:str, llm) -> Classification` with `Classification(oracles:list[str], rationale:str, suspects:list[str])`.

- [ ] **Step 1: Pipeline algorithm** (the budget object is shared across all steps; total usage across classification and all attempts must stay within `Budget`):
  1. `materialize` → `Sandbox.create`.
  2. Existing-test check: `build_variant(plain)`, then run `recipe.test_command` in the sandbox. If it fails, return `skipped` with reason `"existing test already fails; Proofsmith not needed"`. This implements spec section 1.
  3. `repo_summary` = top-level `list_dir`, the first 120 lines of the README if present, and the target names from `compile_commands.json`.
  4. `classify` (one LLM call, JSON only, validated by pydantic). If it's invalid twice, the fallback order is `["asan_ubsan", "tsan", "assertion"]`. Keep at most 2 oracles.
  5. For each oracle in order: run `run_agent` with `proofsmith_system.md + oracle_<oracle>.md + harness_contract.md`, the issue, and the classification rationale. When the agent calls `finish`, **Proofsmith itself** runs `compile_harness` and `run_n(n=RUNTIME_N)` in the oracle's variant, then `decide(k=RUNTIME_K)`. On accept → `freeze` and return `accepted`. On reject → if attempts for this oracle are below 3, send `retry_feedback.md` filled with the decision reason, the evidence kinds histogram and the first failing output, then continue the same conversation. Otherwise move to the next oracle. An agent `abstain` moves to the next oracle.
  6. If nothing is accepted → return `abstained` with reason `"NO VERIFIER: " + "; ".join(per-attempt reasons)`, and freeze an abstention bundle (`status: abstained`, no harness).
  7. Before freezing, `illegal_changes()` must be empty. Otherwise reject the attempt with reason `"harness modified files outside proofsmith_harness/"`.

- [ ] **Step 2: Prompts.** Write them in plain, direct English. They must not contain any case id, function or file name from any dataset; `check_no_tuning.sh` enforces this. Required content:
  - `proofsmith_system.md`: "You construct a failing check for a reported C/C++ bug, before anyone fixes it. You never fix the bug. You write a new program under proofsmith_harness/ that exercises the project's own code so that the selected oracle fires on the current code and would stop firing once the bug is fixed. You cannot edit any other file. Your check will be run N times by an automated judge; it is accepted only if the same oracle report, with the same top application stack frames, appears in at least K of N runs. A check that fails for reasons unrelated to the reported bug is worse than no check. If you cannot build a check that targets the reported behavior, call abstain with a precise reason."
  - `oracle_tsan.md`: TSan reports unordered accesses even when the timing is benign, and reports lock-order inversions even if no deadlock happens. Prefer harnesses that perform the conflicting operations in separate threads with no extra synchronization **between** them, rather than stress loops. For "sometimes hangs/freezes", look for two code paths acquiring the same locks in different orders and drive both paths once each; sequential threads are fine because TSan records the lock-order graph. Do not introduce races in the harness itself: harness-only reports have no application frames and are rejected.
  - `oracle_asan_ubsan.md`: drive the exact API sequence that makes the project read or write freed or out-of-bounds memory, or hit UB (signed overflow, shift, misaligned or null access). Keep the harness deterministic.
  - `oracle_assertion.md`: encode the issue's expected behavior with `PS_CHECK(...)` from `proofsmith_check.h`, on the project's public API, with concrete values from the issue. One focused check beats many.
  - `classify.md`: return JSON `{"oracles": [...], "rationale": "...", "suspects": ["function or file names you'd look at first"]}`, ranking by which oracle gives the most direct, observable evidence for the reported symptom. Allowed values: `tsan`, `asan_ubsan`, `assertion`.
  - `retry_feedback.md`: the judge's verdict template with `{reason}`, `{histogram}`, `{first_failure_excerpt}`, plus one sentence: "Change the harness, not the project."
  - `harness_contract.md`: the Contracts "Harness contract" section, verbatim.

- [ ] **Step 3: Micro cases.** Each is a small CMake library plus tests that pass on buggy, with an issue that describes symptoms only and a hidden fix patch:
  - `uaf-lru`: `LruCache::get` returns `const V&` into a list node; a later `put` evicts it; the caller reads the dangling reference. Issue: "after the cache fills up, prices read right after inserting new symbols are sometimes garbage". Hidden class `lifetime`; the fix returns `std::optional<V>` by value. Expected oracle `asan_ubsan`.
  - `race-stats`: `Stats::record(latency_us)` increments plain `uint64_t` counters from a 4-thread `WorkerPool`. Issue: "request counter in metrics is sometimes lower than requests served". Class `race`; the fix uses `std::atomic`. Expected `tsan`.
  - `ub-notional`: `notional(int32_t px, int32_t qty)` multiplies in `int32_t`. Issue: "very large orders show a negative notional". Class `ub`; the fix widens to `int64_t`. Expected `asan_ubsan` (UBSan).
  - `rounding-ticks`: `to_ticks(double price, double tick)` truncates. Issue: "an order at 0.29 with tick 0.01 rests at 0.28". Class `behavioral`; the fix uses `std::llround`. Expected `assertion`.
  - `vague-perf`: a correct library. Issue: "the matcher feels slower since last week's deploy; nothing specific". Class `none`; no fix. Expected `abstained`.

- [ ] **Step 4: Tests.**
  - `test_classify.py` (FakeLLM): valid JSON is parsed; invalid JSON twice → fallback order; unknown oracle names are filtered out; the result is capped at 2.
  - `test_pipeline_fake.py` (FakeLLM + real builds of orderd; slow):
    - a scripted agent that writes the reference harness and calls finish → `accepted`, with bundle signature kind `tsan:lock-order-inversion`;
    - a scripted agent that writes a harness with its own data race on a harness global → rejected (no app frames), then abstains on retry → overall `abstained`, with the reason containing "no eligible";
    - a scripted agent that edits `order_book.cpp` via `run_shell` → the attempt is rejected for illegal changes;
    - existing tests failing (inject a failing test via a temp copy of the case) → `skipped`;
    - the budget is shared: a scripted usage that exhausts tokens during the first oracle → no second oracle attempted, `abstained` with "budget".
  - `test_micro_cases_build.py` (slow): each micro case builds in all three variants; existing tests pass on buggy; the fix patch applies cleanly; existing tests pass on fixed.
  - `test_live_pipeline.py` (live; run by `gate_phase3.sh`): `make_verifier` with `deepseek-v4-pro` on `orderd-deadlock` and the 5 micro cases. Each accepted bundle is then checked with `verify_bundle` on the hidden fixed tree (n=20). Required outcomes:
    - `orderd-deadlock`: accepted; oracle `tsan`; signature kind `tsan:lock-order-inversion`; `verify_bundle` on the `scoped_cancel` and `consistent_order` trees gives 0/20; on `timing_backoff` ≥ 16/20.
    - `vague-perf`: `abstained`.
    - Of `uaf-lru`, `race-stats`, `ub-notional`, `rounding-ticks`: at least 3 accepted with fixed-tree fails == 0.

    A miss beyond that fails the gate. The phase log must analyze every miss from its trajectory: what the model tried and why the judge rejected it. Do not make prompt edits that reference the missed case.
- [ ] **Step 5:** `scripts/gate_phase3.sh`: runs the live test once (skipping it if `results/verifiers/*/proofsmith.json` already exist for all 6 instances and `--rerun` is not given, so a re-gate costs $0), copies bundles to `results/verifiers/<id>/proofsmith.json`, rebuilds the demo with `harness_source: "proofsmith"`, and prints ledger status. Run the gate: `GATE 3: PASS`.

**Browser checks (phase 3):**
- `B3.1` `/demo/` now shows `[data-testid=harness-source-label]` = `Generated by Proofsmith (deepseek-v4-pro)`, and the matrix still satisfies B1.2–B1.4 with the generated verifier.
- `B3.2` `/verifiers/orderd-deadlock/` shows: the oracle; the signature; a 10-dot run strip with ≥ 8 red; the harness source in a code block; the sha256 of every file; cost and wall time (`data-source`); and a link to the trajectory that resolves (HTTP 200).
- `B3.3` `/verifiers/vague-perf/` shows a `[data-testid=abstain-banner]` whose text starts with `NO VERIFIER:`.
- `B3.4` `/verifiers/` index lists 6 instances with status pills that match the JSON.
- Screenshots: `demo-generated-1280.png`, `verifier-orderd-1280.png`, `verifier-abstain-1280.png`, `verifier-orderd-390.png`.
- Layer B: read the generated harness on the page. In the phase log, say in two sentences whether a C++ engineer would find it a reasonable, minimal check.

**Done when:** the gate passes, spend is at or under $0.75, misses are analyzed, and the work is committed and tagged `phase-3-done`.

---

## Phase 4 — Track B curation: real lifetime and concurrency bugs that build under sanitizers

**Why it matters:** Track B is where the thesis gets proven or killed. The spec calls it the hardest step. Every instance must be real, documented from fetched sources, and build at both commits under both sanitizer variants on this 7 GB machine.

**Spend ceiling:** $0. You triage candidates yourself by reading them. No DeepSeek calls.

**Files:**
- Create: `proofsmith/datasets/mine.py`, `proofsmith/datasets/check.py`, `scripts/trackb_mine.sh`, `data/trackB/candidates.jsonl`, `data/trackB/instances/<id>.json`, `data/trackB/hidden/<id>.json`, `data/trackB/hidden/<id>.fix.diff`, `data/trackB/raw/<id>.issue.json` (raw API response), `data/trackB/REJECTED.md`
- Create: `proofsmith/report/templates/trackb.html.j2`, `tests/phase4/{test_schema.py,test_separation.py,test_trackb_builds.py}`, `scripts/gate_phase4.sh`

**Interfaces:**
- Consumes: `Instance`, `HiddenInstance`, `BuildRecipe`, `materialize`, `build_variant` from Phase 1.
- Produces: `mine(repo_url:str, since:str) -> list[Candidate]`; `check_dataset(track:str) -> CheckReport` (per instance: `schema_ok`, `issue_ok`, `separation_ok`, `builds: {"buggy": {"asan_ubsan": ok, "tsan": ok}, "fixed": {...}}`, `fix_size: {"files": int, "lines": int}`).

- [ ] **Step 1: GitHub access.** `gh` is installed by `setup_root.sh`. Unauthenticated REST is limited to 60 requests/hour. If that's not enough, stop and ask the orchestrator to have the user run `gh auth login` in WSL. Never ask for a token in chat.
- [ ] **Step 2: Mining.**
  - Blobless clones (`git clone --filter=blob:none`) into `~/psw/repos/`. Search, in this priority order (smaller and faster to build first): `cameron314/concurrentqueue`, `gabime/spdlog`, `google/leveldb`, `taskflow/taskflow`, `yhirose/cpp-httplib`, `libuv/libuv`, `uxlfoundation/oneTBB` (check the current org name), `redis/redis`, `facebook/rocksdb`.
  - Use `git log --all -i -E --grep='data race|tsan|threadsanitizer|use[- ]after[- ]free|heap-use-after-free|deadlock|lock[- ]order|race condition|dangling'`.
  - For each candidate record `{repo, sha, parent, subject, files_changed, lines_changed, pr_url?, issue_url?}`. Find linked PR and issue numbers from the commit message, `(#123)` suffixes, and `gh api repos/<o>/<r>/commits/<sha>/pulls`.
- [ ] **Step 3: Acceptance criteria per instance.** All are required; anything rejected goes in `REJECTED.md` with the reason.
  1. Real issue text fetched from the GitHub API and stored raw in `data/trackB/raw/`. If only a PR description exists, write a symptoms-only rewrite in `issue.body` with `rewritten: true`, and store the original in the hidden file. The rewrite must describe observable behavior only (crash, wrong value, hang, TSan/ASan output the reporter saw), never the cause or the fix.
  2. If the issue text names the fix (for example "should use scoped_lock"), set `mentions_fix: true`. These count, but are reported separately.
  3. `buggy` = the fix commit's parent; `fixed` = the fix commit. When the fix spans several commits, use the merge's parents and document it.
  4. The fix touches at most 5 non-test source files and at most 200 changed lines.
  5. Both commits build under `asan_ubsan` **and** `tsan` within 20 minutes each with `jobs: 4`, without OOM on this machine. Record the build recipe in the instance.
  6. `bug_class` ∈ {`deadlock`, `race`, `lifetime`, `ub`}, decided from the fix diff and stored in the hidden file.
  7. Dev tests added by the fix are listed in `dev_tests` (hidden).
- [ ] **Step 4: Target.** At least 12 accepted instances (hard floor 10), at least 4 concurrency (`race` + `deadlock`) and at least 4 `lifetime`. No more than 4 instances from one repo. If after mining all listed repos you have fewer than 10, stop and report counts per rejection reason. The orchestrator decides whether to add repos.
- [ ] **Step 5: Separation.** Visible instance JSON contains only `schema`, `id`, `track`, `source` (url + buggy sha), `issue`, `build`. The fixed sha, the fix diff, `bug_class` and `dev_tests` exist only in `hidden/`.
- [ ] **Step 6: Tests.**
  - `test_schema.py`: every instance and hidden JSON validates; ids are unique; every visible id has a hidden twin.
  - `test_separation.py`: no visible JSON contains its fixed sha (full or the 7-char prefix), any line of 20+ characters from its fix diff, or any `fix_files` basename inside the issue text unless `mentions_fix` is true. No visible JSON mentions `bug_class`.
  - `test_trackb_builds.py` (slow, cached): `check_dataset("B")` shows every build ok. Runs all 4 builds per instance and caches results under `~/psw/cache/`.
- [ ] **Step 7:** `scripts/gate_phase4.sh`: checks that each `issue.url` returns HTTP 200 via `curl -s -o /dev/null -w '%{http_code}'`, and the count and class floors from Step 4. Run the gate: `GATE 4: PASS`.

**Browser checks (phase 4):**
- `B4.1` `/trackb/` table: one row per instance with id, repo, a linked issue (opens GitHub), a rewritten flag, a mentions-fix flag, fix size, and 4 build cells (buggy/fixed × asan_ubsan/tsan), all `.pill-pass`.
- `B4.2` A summary strip shows counts per bug class with `data-source` into `results/trackB_check.json`. This page is internal: bug classes are visible here, but never in prompts.
- `B4.3` Row count equals the number of files in `data/trackB/instances/`.
- Layer B (important): open 3 randomly chosen issue links in the browser. For each, confirm the GitHub page title contains the repo name, and that the issue text on GitHub matches `issue.body` (or that `rewritten: true` is set). Record the 3 ids and the result.
- Screenshots: `trackb-1280.png`, `trackb-390.png`.

**Done when:** the gate passes, `REJECTED.md` explains every rejection, and the work is committed and tagged `phase-4-done`.

---

## Phase 5 — Baselines B0/B1, hidden evaluator, alignment, Track A ingestion

**Why it matters:** Proofsmith must beat **B1**, not B0. B1 is the same model, same tools, same budget, explicitly told to reproduce first with sanitizers available. If a prompt alone matches Proofsmith, Proofsmith is dead, and this phase builds the instrument that decides that. The evaluator is the only component that ever sees fixed code.

**Spend ceiling:** $0.75 (B0 and B1 dry runs on the 6 demo/micro instances).

**Files:**
- Create: `proofsmith/prompts/b0.md`, `proofsmith/prompts/b1.md`, `proofsmith/systems.py`, `proofsmith/eval/evaluator.py`, `proofsmith/eval/alignment.py`, `data/trackA/instances/*.json`, `data/trackA/hidden/*.json`, `proofsmith/datasets/tracka.py`
- Create: `proofsmith/report/templates/eval_instance.html.j2`, `tests/phase5/{test_systems_fake.py,test_evaluator.py,test_alignment.py,test_tracka.py,test_live_baselines.py}`, `scripts/gate_phase5.sh`

**Interfaces:**
- Consumes: `make_verifier`, `run_agent`, `ToolSet`, `Sandbox`, `Budget`, `LLMClient`, `freeze`, `load_bundle`, `verify_bundle`, `materialize`, `apply_patch`, `build_variant`, `parse_evidence`, `Instance`, `HiddenInstance`.
- Produces:
  - `run_system(system:"b0"|"b1"|"proofsmith", instance:Instance, llm, budget:Budget, out_dir:Path) -> Path` (bundle dir)
  - `evaluate(bundle_dir:Path, instance:Instance, hidden:HiddenInstance, work:Path) -> Verdict` (the Contracts Verdict)
  - `changed_functions(buggy_repo:Path, fix_diff:str) -> list[FuncRange]` with `FuncRange(name:str, file:str, start:int, end:int)`
  - `align(evidence_frames:list[Frame], coverage_hits:list[FuncRange]|None, changed:list[FuncRange], repo_root:str) -> Alignment`

- [ ] **Step 1: Baseline prompts.**
  - `b0.md`: "You are working in a snapshot of a C/C++ repository. A user reported the issue below. Write a reproduction test for this issue: a program under proofsmith_harness/ that fails (non-zero exit) on the current code because of the reported bug, and would pass once the bug is fixed. Do not modify any file outside proofsmith_harness/. Do not fix the bug. When done, call finish with the build variant your test needs." Followed by `harness_contract.md`.
  - `b1.md`: B0's text, plus: "Reproduce first: before you call finish, confirm that your program actually fails on the current code, and fails because of the reported bug. Sanitizers are available: build_variant('asan_ubsan') builds the project with AddressSanitizer and UndefinedBehaviorSanitizer; build_variant('tsan') builds it with ThreadSanitizer; run_harness(variant, n) builds and runs your program n times and reports exit codes and parsed sanitizer evidence. Use them whenever they help."
  - All three systems get identical `ToolSet` schemas, identical `Budget`, and the same model. B0 and B1 bundles are frozen at `finish` with `status: submitted`; a budget-exhausted or abstained baseline is frozen as `gave_up`, with whatever harness exists.
- [ ] **Step 2: Evaluator.**
  - For each bundle: `load_bundle` (tamper check); materialize **buggy** and **fixed** trees into fresh `~/psw/eval/<instance>/<system>/{buggy,fixed}`. Fixed = buggy + the hidden fix patch, or a git checkout of the fixed sha.
  - On each tree: `build_variant(bundle.variant)`, copy the harness in, `compile_harness`, `run_n(EVAL_N)`. Fails use the Contracts definition (exit code, signal, timeout); this rule is identical for every system.
  - Compute `f2p`, `evidence_kinds` and alignment. Abstained or skipped bundles get `f2p: false` and `bundle_status` set.
  - The evaluator runs with network on but never inside a sandbox an agent can reach. It is never imported by `systems.py` or `pipeline.py`; a test enforces this.
- [ ] **Step 3: Alignment.**
  - `changed_functions`: parse the unified diff. For each hunk, take the buggy-side line range `[old_start, old_start+old_len)`; for pure insertions use `old_start` and `old_start+1`. Map lines to enclosing functions using `ctags --languages=C,C++ --kinds-C++=f --kinds-C=f --fields=+ne --output-format=json -f - <file>` on the buggy file. The `end` field gives the range. Ignore test files (paths containing `test`).
  - **Strict:** any app frame from any failing buggy run's evidence falls inside a changed function range (file matched by relpath). For assertion bundles, which have no stacks, strict uses coverage: build the `coverage` variant on buggy, run the harness once with `LLVM_PROFILE_FILE`, `llvm-profdata merge`, then `llvm-cov export -format=text`, and collect functions with execution count > 0. Strict holds if any changed function executed. If the coverage run times out, set `unknown: true`, and strict and relaxed are both false.
  - **Relaxed:** any app frame in a changed file, or (assertion) any executed function in a changed file.
  - Report both. Never let alignment change `f2p`; they are separate metrics.
- [ ] **Step 4: Track A ingestion (local builds, no Docker).**
  - Download the Multi-SWE-bench C++ split from Hugging Face. Verify the dataset name and fields by reading its dataset card first; record the URL and the revision hash. Do not assume field names.
  - Select 12 instances across at least 3 of `fmtlib/fmt`, `nlohmann/json`, `catchorg/Catch2`, `yhirose/cpp-httplib`, `simdjson/simdjson`, preferring those that build in under 10 minutes locally with clang.
  - Visible: repo url + base commit + issue text (problem statement). Hidden: `fixed = {"kind":"patch"}` from the dataset's fix patch, `bug_class: "behavioral"` (or what the diff shows), and `dev_tests` from the dataset's F→P list.
  - Build both trees under `plain` **and** `asan_ubsan` to confirm. Use the same separation tests as Track B.
  - `cpp-httplib` tests use loopback sockets. The sandbox brings `lo` up, so they work inside `unshare -rn`. Verify this.
- [ ] **Step 5: Tests.**
  - `test_evaluator.py` (slow, no LLM):
    - The Phase 1 reference bundle on orderd: `f2p: true`, strict aligned (frames in `OrderBook::cancel`, which the fix changes).
    - A planted always-fail bundle (harness `return 1;`): `buggy_fails=20`, `fixed_fails=20`, `f2p: false`.
    - A planted flaky bundle (fails when `std::random_device{}() % 2`): `f2p: false`.
    - A tampered bundle: the error is recorded and `f2p: false`.
    - A bundle whose harness fails to compile on fixed: `build_ok_fixed: false`, `f2p: false`.
    - Assert `systems.py` and `pipeline.py` do not import `proofsmith.eval`.
  - `test_alignment.py` (unit, synthetic):
    - a diff touching lines 10–12 of `a.cpp`, where ctags says `foo` spans 8–20, gives changed = [`foo`];
    - a pure insertion at line 30 inside `bar` (25–40) gives [`bar`];
    - a frame at `a.cpp:15` gives strict true;
    - a frame in `a.cpp` but inside `baz` (unchanged) gives strict false and relaxed true;
    - a coverage timeout gives `unknown: true`.
  - `test_systems_fake.py` (FakeLLM): B0, B1 and Proofsmith all receive identical tool schemas (compare JSON) and identical budgets. B1's system prompt contains "Reproduce first" and B0's does not. A B0 bundle is frozen with `status: submitted` and the declared variant.
  - `test_tracka.py`: 12 Track A instances validate, separation holds, and each builds (cached).
  - `test_live_baselines.py` (live; run by `gate_phase5.sh`): B0 and B1 on the 6 demo/micro instances with `deepseek-v4-pro`, then evaluate all 18 bundles (B0, B1 and the Phase 3 Proofsmith bundles). It asserts that each run completes with a recorded verdict, not specific outcomes. Results go to `results/dryrun/`, which is **not** reported as evaluation results. This is a plumbing test.
- [ ] **Step 6:** `scripts/gate_phase5.sh`: runs the live test once (cached unless `--rerun`), then `proofsmith report build`. Run the gate: `GATE 5: PASS`.

**Browser checks (phase 5):**
- `B5.1` `/eval/dryrun/orderd-deadlock/` shows 3 columns (B0, B1, Proofsmith). Each shows f2p, buggy x/20, fixed x/20, alignment strict/relaxed, oracle or variant, cost, and a trajectory link. All values have `data-source`.
- `B5.2` The alignment panel lists changed functions and, for each hit, the frame or coverage evidence that hit it.
- `B5.3` `/eval/dryrun/` index: a 6×3 grid of f2p pills that match the JSON.
- `B5.4` `/tracka/` mirrors `/trackb/` for Track A (12 rows, builds green).
- Screenshots: `eval-orderd-1280.png`, `eval-grid-1280.png`, `tracka-1280.png`, `eval-orderd-390.png`.
- Layer B: on the orderd eval page, check that a reader can tell in under 10 seconds which system produced an aligned F→P check.

**Done when:** the gate passes, spend is at or under $0.75, and the work is committed and tagged `phase-5-done`.

---

## Phase 6 — Full evaluation run, metrics, kill criteria (requires user approval)

**Why it matters:** these are the numbers that go in the email. They must be produced once, honestly, with the protocol fixed **before** seeing results.

**Spend:** pilot first, then **stop for approval**.

**Files:**
- Create: `proofsmith/eval/runner.py`, `proofsmith/eval/metrics.py`, `results/pilot_cost.json`, `results/eval/<track>/<id>/<system>.json`, `results/summary.json`, `proofsmith/report/templates/results.html.j2`, `tests/phase6/{test_metrics.py,test_runner.py,test_results_complete.py}`, `scripts/gate_phase6.sh`, `docs/protocol.md`

**Interfaces:**
- Consumes: `run_system`, `evaluate`, `Ledger`, `Instance`, `HiddenInstance`, `Budget`.
- Produces: `run_eval(track:str, systems:list[str], instance_ids:list[str]|None, resume:bool) -> None`; `compute_metrics() -> dict` (written to `results/summary.json`).

- [ ] **Step 1: Freeze the protocol** in `docs/protocol.md` and commit it **before** the pilot:
  - the model, the budget, the constants, and the instance lists (Track A and Track B ids);
  - the system order per instance, randomized with seed `20261001` and recorded;
  - one attempt per (instance, system) at temperature 0 where the API accepts it; repeats are unaffordable, and the write-up says so;
  - metric definitions (below) and the kill criteria, copied verbatim from spec section 7.
- [ ] **Step 2: Runner.** Resumable: skip (instance, system) pairs that already have a verdict file. Write the bundle first, then the verdict, so each is written atomically. `BudgetExceeded` stops cleanly. Per-pair errors are recorded in the verdict's `error` field and never retried silently. Retrying a pair is allowed only for infrastructure failures (OOM, a disk-full build failure), and is logged in `results/infra_retries.jsonl`.
- [ ] **Step 3: Pilot.** 2 Track B + 2 Track A instances × 3 systems. Write `results/pilot_cost.json` with per-system mean and max cost and wall time, and a projection for the full run (mean × pairs × 1.3 safety margin). **Stop.** Report the projection and the remaining ledger budget in the phase log. The orchestrator asks the user to approve, top up, or shrink the instance list. Never run the full set without that approval written into `docs/phase-logs/phase-6.md` by the orchestrator.
- [ ] **Step 4: Full run** (after approval): Track B × {b0, b1, proofsmith}, then Track A × {b0, b1, proofsmith}.
- [ ] **Step 5: Metrics** (`compute_metrics`), per track and per system:
  - `n_instances`, `raw_f2p`, `aligned_f2p_strict`, `aligned_f2p_relaxed`, `alignment_unknown`;
  - percentages, with Wilson 95% intervals (formula in code, no scipy);
  - per-oracle breakdown of successes (from bundle `oracle`, or `variant` for baselines);
  - **abstention precision** = abstained instances where B1 is also not F→P ÷ total Proofsmith abstentions;
  - **flake rate on fixed** = bundles with 1 ≤ fixed_fails < 20 ÷ submitted-or-accepted bundles;
  - median wall and cost;
  - a paired comparison of Proofsmith vs B1 on aligned_f2p_strict: discordant counts b (Proofsmith only) and c (B1 only), with an exact two-sided McNemar p-value = `min(1, 2 * sum(comb(b+c, i) for i in range(0, min(b,c)+1)) / 2**(b+c))`.

  **Kill criteria:**
  - Track B verdict `PASS` if `aligned_strict_pct(proofsmith) − aligned_strict_pct(b1) ≥ 20` points, else `KILL_OR_RETHINK`.
  - Track A verdict `OK` if `raw_pct(proofsmith) ≥ raw_pct(b1) − 5`, else `RESTRICT_TO_LIFETIME_CONCURRENCY`.
- [ ] **Step 6: Tests.**
  - `test_metrics.py`: synthetic verdicts give exact expected numbers (Wilson bounds to 1e-6; McNemar for b=5, c=0 → p=0.0625; b=3, c=3 → p=1.0); kill-criteria edges at exactly +20 → PASS, and 19.9 → KILL_OR_RETHINK.
  - `test_runner.py`: interrupting after 2 pairs (FakeLLM) then resuming gives no duplicate verdicts and the same final set; `BudgetExceeded` mid-run leaves no half-written verdicts.
  - `test_results_complete.py`: every (instance, system) in `docs/protocol.md` has a verdict or an error record; `summary.json` validates against its schema.
- [ ] **Step 7:** `scripts/gate_phase6.sh` checks `test_results_complete` and that `results/summary.json` is newer than every verdict. Run the gate: `GATE 6: PASS`.

**Browser checks (phase 6):**
- `B6.1` `/results/` shows per-track tables with rows B0, B1, Proofsmith and columns raw F→P, aligned strict, aligned relaxed, abstentions, flake on fixed, median cost, median wall. Every number has `data-source` into `results/summary.json`.
- `B6.2` A kill-criteria badge for each track shows the verdict string exactly as in the JSON (`PASS`, `KILL_OR_RETHINK`, `OK`, `RESTRICT_TO_LIFETIME_CONCURRENCY`).
- `B6.3` The per-oracle breakdown chart (an inline SVG bar chart, no libraries) has one bar group per oracle, with bar heights proportional to counts (check each `height` attribute against the JSON).
- `B6.4` Every instance link from the results tables resolves (HTTP 200), and each instance page passes the B5.1 assertions.
- Screenshots: `results-1280.png`, `results-390.png`, `oracle-chart-1280.png`.
- Layer B: click through 3 instance pages from the results table and confirm the numbers on each agree with the summary row.

**Done when:** the gate passes, the pilot approval is recorded, and the work is committed and tagged `phase-6-done`.

---

## Phase 7 — Write-up, worked cases, send-ready package, one-command reproduction

**Why it matters:** ByteAsk's CTO will spend about two minutes deciding whether this is serious. Every number must be traceable, every claim about ByteAsk must be verified, and he must be able to reproduce the verdicts with one command and without an API key.

**Spend:** $0.

**Files:**
- Create: `README.md` (generated), `proofsmith/report/readme.py`, `proofsmith/report/templates/README.md.j2`, `scripts/reproduce.sh`, `docs/send_message.md` (generated), `docs/worked_cases/{sanitizer_win,plain_test_win,honest_failure}.md`, `proofsmith/report/templates/landing.html.j2`, `tests/phase7/{test_readme_numbers.py,test_claims.py,test_reproduce.py,test_send_message.py}`, `scripts/gate_phase7.sh`

- [ ] **Step 1: One-command reproduction.**
  - `scripts/reproduce.sh` with no arguments: from a fresh clone, runs setup checks, the orderd demo, and the evaluator over every frozen bundle in `results/verifiers/` and the evaluation bundles. It prints a table, and exits 0 only if every recomputed verdict equals the committed one. **No API key needed.**
  - `scripts/reproduce.sh --with-agents` reruns the systems (needs a key, costs money, and prints the projected cost first).
- [ ] **Step 2: Worked cases.** Choose from results:
  - one sanitizer win, where Proofsmith is aligned F→P with a sanitizer oracle and B1 is not;
  - one plain-test win, where Proofsmith uses the assertion oracle, or where B1 wins on a behavioral bug (that's fine and honest);
  - one honest failure, where Proofsmith abstained or failed, with the reason.

  Each case document includes the issue excerpt, what each system did (from trajectories), the evidence (a raw report excerpt), and the verdicts. Numbers come only from template variables filled from JSON.
- [ ] **Step 3: README** (generated by `proofsmith report readme`):
  - the one-sentence pitch from spec section 12;
  - the demo matrix;
  - one results table per track;
  - the kill-criteria verdicts;
  - the three worked cases (linked);
  - reproduce commands;
  - limitations (spec section 11, plus the actual TSan suppression count, the single-attempt caveat, Track B size, and that rr is out of scope);
  - claims used (C-ids with links).

  If Track B's verdict is `KILL_OR_RETHINK`, the README says so in the first screen and pivots to "an open benchmark and an honest negative result". It doesn't hide it.
- [ ] **Step 4: Send message.** `docs/send_message.md` is filled from spec section 10's template using `results/summary.json`. Every `__` is replaced by a number from JSON. There is a second template for the negative-result case. Both are under 120 words. Only VERIFIED claims may appear.
- [ ] **Step 5: Landing page** (`site/index.html` becomes the pitch). It has:
  - a hero with the one sentence;
  - the demo matrix, embedded from Phase 1 data;
  - the results summary;
  - "What this is for ByteAsk": three bullets, each tied to a VERIFIED claim id (C2/C3 for the gap; C4/C5 for integration);
  - worked cases;
  - reproduce;
  - limitations.

  The toolchain doctor moves to `/toolchain/`.
- [ ] **Step 6: Tests.**
  - `test_readme_numbers.py`: every number in `README.md` and `docs/send_message.md` appears in the JSON it claims to come from (the generator emits a sidecar `README.sources.json` mapping each number to its pointer; the test re-resolves every pointer).
  - `test_claims.py`: every sentence in README, landing page and send message containing "ByteAsk" cites a claim id that is VERIFIED in `docs/claims.md`. Any `U<n>` claim id appearing in an output fails. You may verify U1–U4 now by fetching their sources; on success, move them to VERIFIED with URL, quote and date.
  - `test_reproduce.py` (slow): `git clone ~/proofsmith ~/psw/clean-clone && cd ~/psw/clean-clone && bash scripts/reproduce.sh` exits 0 with `DEEPSEEK_API_KEY` unset.
  - `test_send_message.py`: no `__` remains; at most 120 words; the variant matches the Track B verdict.
- [ ] **Step 7:** `scripts/gate_phase7.sh` runs a link check over the site (every internal link 200; every external link HEAD 200 or 301/302). Run the gate: `GATE 7: PASS`.

**Browser checks (phase 7):**
- `B7.1` `/` at 1280×800: the hero sentence and the first row of the demo matrix are visible without scrolling (both elements' bounding-box bottom ≤ 800).
- `B7.2` `/` at 390×844: no horizontal overflow; the matrix becomes a stacked card layout; tap targets ≥ 44px high.
- `B7.3` Every number on `/` has a `data-source` that verifies.
- `B7.4` Every `data-claim` on `/` refers to a VERIFIED claim; its link opens the cited URL.
- `B7.5` Every `<img>` and `<svg>` has `alt` or `aria-label`; headings go h1 → h2 → h3 with no skips.
- `B7.6` `/toolchain/`, `/demo/`, `/results/`, `/trackb/`, `/tracka/`, `/runs/` and `/verifiers/` all load with zero console errors.
- Screenshots: `landing-1280.png`, `landing-390.png`, `landing-full-1280.png` (full page).
- Layer B: read the landing page top to bottom as ByteAsk's CTO. In the phase log, write the three things he would doubt first, and point to where the page answers each. If it doesn't, fix the page.

**Done when:** the gate passes, `reproduce.sh` works from a clean clone, and the work is committed and tagged `phase-7-done`. **This is the send-ready state.**

---

## Phase 8 — Gate experiment (only if Track B verdict is PASS, and the user approves spend)

**Why it matters:** the spec's week-2 claim is that patches can pass the repo's tests and still fail the frozen check. This phase counts them, then separates true catches from an over-strict verifier using the hidden dev tests.

**Files:** `proofsmith/prompts/patcher.md`, `proofsmith/gate_experiment.py`, `results/gate/<id>.json`, `results/gate_summary.json`, `proofsmith/report/templates/gate.html.j2`, `tests/phase8/{test_gate_categories.py,test_gate_complete.py}`, `scripts/gate_phase8.sh`

- [ ] **Step 1: Patcher.** The same loop and model, with a write scope of the whole repo **except** `proofsmith_harness/` (inverted rule). It gets the issue and the snapshot; it never sees V. Prompt: "Fix the reported bug. Keep the change minimal. Run the existing tests. Call finish when done." It produces a diff.
- [ ] **Step 2: Per Track B instance**, apply the patch to buggy, then:
  1. run the existing tests;
  2. run the frozen Proofsmith V (n=20);
  3. apply the dev tests from the fixed commit (hidden; test files only) and run them.

  Categories:
  - `true_catch`: existing pass, V fail, dev fail;
  - `over_strict`: existing pass, V fail, dev pass;
  - `agree_pass`: existing pass, V pass, dev pass;
  - `missed`: existing pass, V pass, dev fail;
  - `broken`: existing fail.
- [ ] **Step 3 (optional, if budget allows): gated mode.** The patcher can call `run_harness` on V and must make it pass. Compare dev-test pass rates gated vs ungated.
- [ ] **Tests:** category logic on synthetic tuples (all 5); completeness (every Track B instance has a result or error).
- **Browser checks:**
  - `B8.1` `/gate/` shows a 5-category table with `data-source`.
  - `B8.2` Each `true_catch` row links to the patch diff and the V failure report.
  - Screenshots: `gate-1280.png`.
- **Done when:** the gate passes; README and landing are regenerated with the gate numbers; the work is tagged `phase-8-done`.

---

## Phase 9 — ByteAsk integration and benchmark release

**Why it matters:** this phase shows the result can plug into ByteAsk tomorrow. ByteAsk connects MCP servers (C4) and has a headless `byteask exec` with JSONL output (C5).

**Files:** `proofsmith/mcp_server.py`, `scripts/byteask_gate.sh`, `benchmark/README.md`, `benchmark/LICENSES.md`, `tests/phase9/{test_mcp.py,test_benchmark_export.py}`, `scripts/gate_phase9.sh`

- [ ] **Step 1: MCP server** (`proofsmith mcp`, stdio, using the official `mcp` Python SDK) with tools:
  - `make_verifier(repo_path, issue_title, issue_body)` → status, oracle, signature, bundle path, and abstain reason;
  - `verify(bundle_path, repo_path)` → fails/n and evidence kinds.

  Test with the SDK's client over stdio against orderd, using a FakeLLM via env flag `PROOFSMITH_FAKE_LLM=reference`.
- [ ] **Step 2: `scripts/byteask_gate.sh "<issue file>" "<task>"`.**
  1. `make_verifier`;
  2. `byteask exec "<task>"` (JSONL captured);
  3. `verify` on the resulting tree;
  4. print `GATED: PASS` or `GATED: FAIL (<evidence>)`.

  Installing and signing in to ByteAsk needs the user (email magic link). Stop and ask the orchestrator, and never automate the sign-in. If the user declines, ship the script with a recorded dry run against a stub `byteask` that applies the Phase 1 `scoped_cancel` and `timing_backoff` patches, and say so plainly.
- [ ] **Step 3: Benchmark export.** `benchmark/` contains Track B visible and hidden splits, the evaluator CLI (`proofsmith evaluate`), per-repo license notes, and the frozen bundles from all systems as reference baselines.
- **Tests:** MCP round-trip; the export has no hidden data in the visible split (reuse the separation tests); `proofsmith evaluate` runs from `benchmark/` alone.
- **Browser checks:**
  - `B9.1` `/integrate/` shows the MCP config snippet for ByteAsk and a transcript of a gated run (or a clearly labeled stub run).
  - `B9.2` `/benchmark/` lists instances and download links that resolve.
  - Screenshots: `integrate-1280.png`, `benchmark-1280.png`.
- **Done when:** the gate passes and the work is tagged `phase-9-done`.

---

## Orchestrator protocol (between phases)

1. Dispatch the executor with this prompt:

   > Execute Phase `<N>` of `docs/superpowers/plans/2026-10-01-proofsmith.md`. Read: Global Constraints, Executor Rules, Contracts, Phase `<N>`. Repo: `C:\Users\Profile 1\ByteAskEval`. Use `.\scripts\ws.ps1` for every WSL command. Stop when `GATE <N>: PASS` and the phase log is written.

2. Review: the gate output in the phase log (rerun the gate yourself), the diff (`git diff phase-<N-1>-done..phase-<N>-done --stat`, then spot-read the core files), the screenshots, the deviations, and the spend.
3. Reject the phase if any of these is true: the gate was modified to pass; a test was weakened without an `xfail` plus a logged deviation; prompts mention dataset specifics; a number on a page lacks `data-source`; spend exceeded the ceiling.
4. User touchpoints: Phase 4 (`gh auth login` if rate-limited), Phase 6 (budget approval after the pilot), Phase 8 (spend approval), Phase 9 (ByteAsk sign-in).

## Self-review against the spec

- Spec §1 (skip when an existing test fails) → Phase 3, pipeline step 2 (`skipped`).
- §2 oracles (assertion, ASan+UBSan, UBSan, TSan race, TSan lock-order) → Phases 0/1 probes and parser; Phase 3 prompts. The rr handoff is out of scope locally (no PMU in WSL2) and stated in the README limitations.
- §5.1 separate ASan+UBSan and TSan builds; harness as a new target; never edit existing tests → `VARIANTS`, the harness contract, and `illegal_changes`.
- §5.2 runtime k-of-n with a fault-type + top-3-frames signature; evaluation fixed 0/20 → `decide`, signature rules, `evaluate`.
- §5.3 alignment (raw and aligned F→P) → Phase 5 alignment; Phase 6 metrics.
- §5.4 abstention plus abstention precision → Phase 3 abstain; Phase 6 metric.
- §6 architecture (build once → compile_commands → classify → instrumented build → harness → run n → accept/freeze or retry/abstain) → Phase 3 Step 1.
- §7 hidden evaluator, Tracks A/B, B0/B1 with the same model/budget, all metrics, kill criteria → Phases 4–6.
- §8 week-1 scope; "not in week 1" items (patch generation, gating, rr, integration, dashboards) → Phases 8–9 only. The static evidence pages are not a dashboard product; they exist so each phase can be verified in a browser.
- §9 weeks 2–4 → Phases 8–9.
- §10 send message from real numbers → Phase 7 Step 4.
- §11 risks: TSan suppressions are counted and reported; small-n stats come with Wilson intervals and McNemar; slow builds are mitigated by caching and `jobs: 4`; over-strict verifiers are measured in Phase 8; unverified claims are blocked by `test_claims.py`.
