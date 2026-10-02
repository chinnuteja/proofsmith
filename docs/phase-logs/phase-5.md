# Phase 5 log
## Result
GATE 5: PASS

```
== pytest tests/phase0..phase5
...................................................................      [100%]
67 passed, 3 deselected in 454.10s (0:07:34)
== phase-specific checks
live dry run skipped (results/dryrun/SKIP_LIVE)
/mnt/c/Users/Profile 1/ByteAskEval/site/index.html
spent: $0.608922
cap: $4.50
remaining: $3.891078
balance: $4.67
== no case-specific prompt tuning
check_no_tuning: OK
== browser gate
/mnt/c/Users/Profile 1/ByteAskEval/site/index.html
serve: OK
BROWSER 5: PASS
GATE 5: PASS
```

## What was built
- proofsmith/prompts/b0.md: write a harness that fails on the current bug; do not fix it.
- proofsmith/prompts/b1.md: B0 plus "Reproduce first" and sanitizer tools.
- proofsmith/systems.py: B0, B1, and Proofsmith share ToolSet schemas, Budget, and model. Baselines freeze as submitted or gave_up.
- proofsmith/eval/evaluator.py: hidden evaluator materializes buggy and fixed trees, runs EVAL_N, records f2p separately from alignment. systems.py and pipeline.py do not import this package.
- proofsmith/eval/alignment.py: changed_functions via unified diff + ctags; strict and relaxed hits.
- proofsmith/datasets/tracka.py: 12 Multi-SWE-bench C++ instances, local clang builds, no Docker.
- data/trackA/: instances, hidden twins, fix diffs, SOURCE.md. Dataset card https://huggingface.co/datasets/ByteDance-Seed/Multi-SWE-bench revision 56ff018c04a38e27ada1e9d0a6d5839a51f88f0d.
- data/trackB/EXCLUDED.md: httplib-2492 stays on the Track B page and is not scored.
- proofsmith/report/templates/eval_index.html.j2, eval_instance.html.j2, tracka.html.j2: /eval/dryrun/ 6×3 grid, per-instance three-column verdicts, /tracka/ build table.
- scripts/gate_phase5.sh: cached live dry run unless SKIP_LIVE or --rerun, then report build and ledger.
- scripts/fill_dryrun.py: writes skipped B0/B1 verdicts and evaluates remaining Proofsmith (and race-stats B0) locally with no extra API calls.
- scripts/tracka_header_build.sh: smoke compile for header-only json/Catch2 so CMake still yields compile_commands.json.
- scripts/tracka_ingest.py: selected 12 records into data/trackA/.
- tests/phase5/: fake systems, evaluator, alignment, Track A, live baselines (deselected under `not live`).
- results/dryrun/: 18 verdict files. results/dryrun/SKIP_LIVE records that later B0/B1 pairs were not live-run.
- results/trackA_check.json: 12 instances, all four builds green.
- proofsmith/agent/loop.py: MAX_RESPONSE_TOKENS 4096 → 16384 so reasoning is not cut mid-reply.

## Browser checks
- B5.1: PASS. `/eval/dryrun/orderd-deadlock/` has three columns (B0, B1, Proofsmith). Each shows f2p, buggy x/n, fixed x/n, alignment strict/relaxed, oracle, cost, and a trajectory link. All values have `data-source`.
- B5.2: PASS. Alignment panel lists changed functions `add` and `cancel` in `order_book.cpp`, and hits through TSan frames in `OrderBook::cancel`.
- B5.3: PASS. `/eval/dryrun/` is a 6×3 grid of f2p pills that match the JSON.
- B5.4: PASS. `/tracka/` has 12 rows, each with four `.pill-pass` build cells.
- Screenshots: docs/evidence/phase-5/eval-orderd-1280.png, eval-orderd-390.png, eval-grid-1280.png, eval-grid-390.png, tracka-1280.png, B5.1-1280.png, B5.1-390.png, B5.2-1280.png, B5.2-390.png, B5.3-1280.png, B5.3-390.png, B5.4-1280.png, B5.4-390.png.
- Layer B: opened http://127.0.0.1:8765/eval/dryrun/orderd-deadlock/. Within a glance: B0 fail-to-pass false (0/0, gave up); B1 fail-to-pass true, 20/20 buggy and 0/20 fixed, alignment strict true; Proofsmith the same plus oracle tsan. B1 and Proofsmith both produced an aligned F→P check. B0 did not. The page lede says these numbers are not the evaluation.

## Spend
- Ledger before: $0.161211 after: $0.608922 phase ceiling: $0.75
- This phase spent $0.447711. Under the $0.75 ceiling. live_balance $4.67. Remaining ledger $3.891078.

## Deviations from plan
- Live B0/B1 on later micros were stopped so remaining DeepSeek credit can go to Track B. `results/dryrun/SKIP_LIVE` makes `gate_phase5.sh` skip the live pytest. `scripts/fill_dryrun.py` wrote skipped verdicts with error `not run: remaining DeepSeek credit reserved for Track B` for race-stats b1 and both b0/b1 on ub-notional, rounding-ticks, and vague-perf. Proofsmith bundles from Phase 3 were evaluated locally. race-stats B0 had a live bundle and was evaluated locally. The live test still asserts that 18 verdict files exist; it does not assert outcomes. Dry-run numbers are plumbing, not evaluation.
- `MAX_RESPONSE_TOKENS` is 16384. At 4096, B0 on orderd was cut mid-reasoning and spent $0.26 to give up.
- Eval oracle `data-source` uses `#/oracle` when the verdict has no `variant` field, so B0/B1 gave-up rows still satisfy the browser check.
- The dry-run grid table reuses the Track B mobile card layout so 390px does not overflow.
- One-shot Track A disk/debug scripts under `scripts/tracka_*.sh` are not part of this commit.

## Open issues for the orchestrator
- Remaining credit (~$3.89 ledger, $4.67 live) is reserved for a small Track B sample: B1 vs Proofsmith, skip B0, skip httplib-2492. That is not Phase 6. Do not claim a +20 point lift on n=4.
- B1 already matches Proofsmith on the synthetic orderd deadlock. Track B is the only honest comparison left on this budget.
- httplib-2492 remains excluded from scoring (TLS off, destructor not compiled).
- uaf-lru B0/B1 submitted but `build_ok_fixed` is false on B1 (harness depends on a removed API). Dry-run only.
- Vague-perf Proofsmith abstained, as designed.
