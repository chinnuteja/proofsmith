# Phase 1 log

## Result
GATE 1: PASS

```
== pytest tests/phase0..phase1
........................                                                 [100%]
24 passed in 387.82s (0:06:27)
== phase-specific checks
orderd.json: schema OK
== no case-specific prompt tuning
check_no_tuning: OK
== browser gate
/mnt/c/Users/Profile 1/ByteAskEval/site/index.html
serve: OK
BROWSER 1: PASS
GATE 1: PASS
```

## What was built
- `cases/orderd/`: buggy order book (ctest 3/3), symptoms-only issue, hidden `scoped_lock` fix, and the three variant patches
- `cases/orderd/stress/stress.cpp`: 300 ms two-trader plus risk-sweep repro, 5 s timeout, 20 runs
- `cases/orderd/reference_harness/`: sequential hand-written harness; TSan reports lock-order-inversion without a hang
- `proofsmith/oracles/signature.py`: `parse_evidence`, `normalize_function`
- `proofsmith/oracles/runner.py`: `run_n`
- `proofsmith/oracles/acceptance.py`: `decide`
- `proofsmith/oracles/builds.py`: `build_variant` (cmake/make/custom) with a build cache under `~/psw`
- `proofsmith/harness.py`: `compile_harness`
- `proofsmith/freeze.py`: `freeze`, `load_bundle`, `verify_bundle`
- `proofsmith/datasets/schema.py`: `Instance`, `HiddenInstance`, `BuildRecipe`, `materialize`, `apply_patch`
- `proofsmith/demo.py`: `proofsmith demo orderd` writes `results/demo/orderd.json`
- `proofsmith/report/templates/demo.html.j2`: `/demo/` matrix, data-source on every number, label "Reference harness (hand-written)"
- `tests/phase1/`: signature, acceptance, freeze, builds, demo
- `scripts/gate_phase1.sh`: JSON Schema check
- `proofsmith/toolchain.py`: doctor kinds come from `parse_evidence`

## Browser checks
- B1.1: PASS, issue body matches `cases/orderd/instance.json`
- B1.2: PASS, 4 body rows × 3 result columns, each cell's numbers match its data-source
- B1.3: PASS, timing backoff row has existing tests `.pill-pass` and Proofsmith check `.pill-fail`
- B1.4: PASS, scoped_cancel Proofsmith check is `0/20` with `.pill-pass`
- B1.5: PASS, run strip has 10 red dots
- B1.6: PASS, raw report contains `lock-order-inversion` and `OrderBook::`
- B1.7: PASS, label text is `Reference harness (hand-written)`
- B1.8: PASS, external links are `https://byteask.ai/` with `data-claim` C2 and C3 only
- Screenshots: `docs/evidence/phase-1/demo-1280.png`, `docs/evidence/phase-1/demo-390.png`, `docs/evidence/phase-1/demo-matrix-1280.png`, plus the per-check shots in that directory
- Layer B: The page makes the point immediately. The opening sentence says existing tests stay green and the frozen check stays red through a timing backoff, and the matrix shows that row at 3/3, stress 20/20, Proofsmith check 20/20, while ByteAsk's `scoped_lock` fix and consistent lock order are 0/20 on the check. A reader does not need the raw report.

## Spend
- Ledger before: $0.00 (no ledger yet; Phase 2 creates it)  after: $0.00  phase ceiling: $0.00
- No DeepSeek calls.

## Deviations from plan
- Build cache key is `(tree hash, source-directory hash, variant)`, not only `(tree hash, variant)`. A content-only cache reused objects compiled for a different directory, so TSan frames were outside the tree under test and `decide` dropped them. Evidence: the first `proofsmith demo orderd` still printed `buggy: ctest 3/3 stress 20/20 verifier 20/20` (and the same 20/20 and 0/20 pattern on the other rows), but `results/demo/orderd.json` at that moment had `"accepted": false` and `"reason": "no eligible tsan evidence in 10 runs"` with `"signatures": {}`. The stacks in that run were from `/home/chinnu/psw/smoke-orderd/...`, not the demo tree. After the path was added to the cache key, the gate run accepted `tsan:lock-order-inversion|orderd::OrderBook::cancel@order_book.cpp|orderd::OrderBook::cancel@order_book.cpp|orderd::OrderBook::risk_sweep@order_book.cpp` in 10/10 runs. The second `build_variant` call in `test_builds.py` is still a cache hit under 2 s.
- `build_variant` copies a tree into `~/psw/cache/src/<hash>` before cmake when the path is not already under `~/psw`, contains a space, or is under `/mnt/`. `cases/orderd/buggy` resolves to `/mnt/c/Users/Profile 1/ByteAskEval/...`. This follows the global constraint that C++ builds stay on the Linux filesystem with no spaces. I did not capture a failing in-place cmake log; the demo trees themselves are built in place under `~/psw/demo/orderd/`.

## Open issues for the orchestrator
- The stress repro deadlocks on every run for `buggy` and `timing_backoff` (20/20 timeouts) and on none of the runs for `scoped_cancel` and `consistent_order` (0/20). Those are the measured numbers, not the placeholder zeros in the plan. No decision needed unless a later phase wants a repro that only sometimes hangs.
- Nothing else blocks Phase 2.
