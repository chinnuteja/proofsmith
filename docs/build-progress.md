# Build progress

The project targets a reproducible C/C++ verifier-generation experiment and a useful integration artifact. Impressing the intended company depends on measured results and reproducibility; an implementation alone does not establish comparative performance.

## Implemented during the continuation

- Git fix diffs now reach alignment; LLVM's function-level coverage JSON is parsed correctly; assertion failures flush coverage before aborting.
- Diff context does not count as a changed function. Build recipe and compiler flags participate in cache keys. Project build errors are separate from existing-test skips; skipped runs produce bundles.
- Generated shell commands, harness builds, and verifier execution use filesystem allowlists, environment filtering, and network namespaces. Bundle freezing rejects symlinks instead of following them into host files. Existing tests write into disposable build copies.
- Protocol hashing, deterministic execution order, resumable atomic results, single-attempt interruption records, pilot costing, paired metrics, Wilson intervals, exact McNemar, and completeness checks.
- Evaluation, metrics, offline replay, and local verify CLI commands. Historical exploratory observations remain separate from protocol-bound results.
- Data-backed results and instance pages, an honest landing page, generated README with numeric-source sidecars, draft outreach, and pending worked-case pages.
- Actual official-SDK MCP stdio round trip with a clearly labelled hand-written reference fixture. The frozen verifier fails on buggy orderd and passes on the fixed program.
- Headless integration script, benchmark export, upstream license inventory, and reproduction command.

## Evidence and remaining gates

Targeted offline regression sets passed; the broader regression suite and browser preview checks are recorded in the continuation log. The existing spdlog baseline's raw fail-to-pass result was reproduced offline without changing its historical verdict.

The four missing real baseline dry-run observations are now complete. The continuation plumbing test passed in 954.70 seconds; its generation cost was $0.123041688, within the additional $0.75 ceiling. Phase 5's historical ceiling failure is preserved, and its old tag is not treated as proof of that historical gate. Outcomes and sources are in `docs/phase-logs/dryrun-continuation-2026-10-03.md`.

Phase 6's dry-run plumbing check is complete. The protocol and implementation were committed at `4fff7ff` before the approved pilot began. The pilot is running; its cost projection, explicit full-run budget approval, and complete experiment remain. The implementation preview does not pass this experimental gate.

Phase 7 cannot be called send-ready until a clean-clone full replay passes and qualifying worked cases are filled from real outcomes. The generated outreach is a draft while the experiment is incomplete.

Phase 8 remains conditional on Track B PASS and separately approved spend. No patch-correctness catch count has been claimed.

Phase 9's local stdio integration is tested. A signed-in end-to-end run with the actual headless product, and a publication/license review of the benchmark package, remain outstanding. No message has been sent and no package has been published.
