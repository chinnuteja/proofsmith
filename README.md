# Proofsmith

Proofsmith makes a C/C++ coding agent earn its green checkmark. Before touching the code, it turns the bug report into a toolchain-backed failing check, freezes it, and abstains when the evidence is insufficient.

**Status: evaluation incomplete. Comparative performance has not been established.**


The earlier pilot recorded 12 observations, 0 fail-to-pass successes, and 7 token-limit violations. [Original outcomes and cost](docs/phase-logs/pilot-outcome-2026-10-03.md) are preserved. The repaired protocol is prepared offline; its pilot has not been authorized or run. [Repair and limitations](docs/repairs/README.md).


The intended integration is relevant to ByteAsk's documented MCP support ([C4](https://docs.byteask.ai/docs/overview)) and headless `exec` interface ([C5](https://docs.byteask.ai/docs/overview)). The local stdio integration is tested separately from the comparative experiment.

## A controlled demonstration

This is a synthetic order-book fixture. It demonstrates why passing existing tests can miss a failure; it is separate from real-issue benchmark scores.


| Program variant | Existing tests passed / total | Stress failures / runs | Frozen verifier failures / runs |
|---|---|---|---|
| buggy | 3 / 3 | 20 / 20 | 20 / 20 |
| timing_backoff | 3 / 3 | 20 / 20 | 20 / 20 |
| scoped_cancel | 3 / 3 | 0 / 20 | 0 / 20 |
| consistent_order | 3 / 3 | 0 / 20 | 0 / 20 |



## Frozen-protocol experiment


### Track A: INCOMPLETE

| System | Observed / expected | Raw F→P | Aligned strict | Aligned relaxed | Median USD |
|---|---|---|---|---|---|
| b0 | 0 / 12 | 0 | 0 | 0 | pending |
| b1 | 0 / 12 | 0 | 0 | 0 | pending |
| proofsmith | 0 / 12 | 0 | 0 | 0 | pending |


Counts use observed runs. Missing runs are not failures. Wilson intervals, paired McNemar results, abstention precision, and fixed-tree flake rates are in [summary.json](results/summary.json). Historical exploratory samples and micro-case plumbing tests never enter these tables.

### Track B: INCOMPLETE

| System | Observed / expected | Raw F→P | Aligned strict | Aligned relaxed | Median USD |
|---|---|---|---|---|---|
| b0 | 0 / 11 | 0 | 0 | 0 | pending |
| b1 | 0 / 11 | 0 | 0 | 0 | pending |
| proofsmith | 0 / 11 | 0 | 0 | 0 | pending |


Counts use observed runs. Missing runs are not failures. Wilson intervals, paired McNemar results, abstention precision, and fixed-tree flake rates are in [summary.json](results/summary.json). Historical exploratory samples and micro-case plumbing tests never enter these tables.


## Reproduce and integrate

Run in Linux or WSL with clang, LLVM coverage tools, CMake, Ninja, ctags, bubblewrap, Python and the package installed. The initial checkout of upstream source commits may require network access.

```bash
python -m pip install -e '.[dev,mcp]'
bash scripts/reproduce.sh
# Replay one bundle and preserve the old verdict:
proofsmith replay --check --bundle results/eval/B/spdlog-1570/b1
# Run the optional stdio server:
proofsmith mcp
```

Offline replay requires no model credentials. It exits nonzero when the recomputed outcome differs. Corrected historical alignment references are documented in [alignment_migration.json](results/alignment_migration.json), with original verdicts archived byte for byte and raw outcomes preserved. Inspect [replay_summary.json](results/replay_summary.json). A passing clean-clone replay is required before calling this release send-ready.

Live generation uses the configured model and ledger. `proofsmith evaluate --pilot` is the pilot; a full run requires the pilot projection and a recorded budget approval. See [protocol](docs/protocol.md).

Worked cases: [sanitizer win](docs/worked_cases/sanitizer_win.md), [plain-test win](docs/worked_cases/plain_test_win.md), [honest failure](docs/worked_cases/honest_failure.md). Pending pages are explicitly labelled.

## Limits

This is a small, single-model, single-attempt experiment. The comparison must beat the strong reproduce-first baseline under identical tools and shared budgets. A sanitizer report must include application frames. Assertions can be accepted without stacks, but evaluation requires real coverage to score alignment.

Generated commands, harness builds and verifier executions receive an explicit filesystem allowlist, a filtered environment, and isolated networking with loopback. The evaluator alone materializes hidden fixed trees. Runtime acceptance does not establish fail-to-pass or patch correctness. Developer-test gate experiments remain conditional on a successful evaluation and separately approved spend. rr is outside the local WSL scope. Current variants use no TSan suppression file.

For technical definitions, costs, and status, see [implementation plan](docs/superpowers/plans/2026-10-01-proofsmith.md), [claims ledger](docs/claims.md), and [build progress](docs/build-progress.md).
