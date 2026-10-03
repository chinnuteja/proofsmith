# Authorized continuation — 2026-10-03

User authorized building the remaining project. Work proceeded on offline implementation and verification. Existing user changes and historical results were retained.

## Verified so far

- Initial alignment tests: 5 passed.
- New real coverage and Git-diff regressions: 4 passed.
- Metric unit tests: 6 passed.
- Isolation and evaluator test set: 24 passed; one historical live smoke test refused to start at its old ceiling before making a request.
- Pipeline and runner/isolation regression set: 17 passed.
- Actual MCP stdio, report provenance, runner and metrics set: 16 passed. MCP uses the explicit reference fixture, not a claimed model-generated benchmark win.
- Existing spdlog B1 replay: buggy 20 failures, fixed 0 failures, raw F→P true, strict alignment false; stored outcome matched.

Generated-code isolation initially made CTest's read-only cache log writes fail. The fix runs existing tests in a disposable copy, preserving the read-only compiler cache. A mistaken MCP test patch path was corrected and the complete round trip rerun successfully.

## Experimental status

No paid request was made during the offline work. Its ledger spend is recorded in `results/preflight.json`. Paid dry-run continuation started only after the subsequent explicit payload/destination approval. Protocol scores are incomplete. Phase 5, the full Phase 6 gate, clean-clone reproduction, and a send-ready release have not been asserted.

The repository plan's Phase 6 states: "Spend: pilot first, then stop for approval" and "Never run the full set without that approval written into docs/phase-logs/phase-6.md." The current preparation adds an explicit approval record tied to the protocol hash. No approval file was created on the user's behalf.

Broader offline-suite and browser-check output will be appended after verification completes.

The broader offline suite initially returned 82 passed and one failure: the old system-budget test expected an extra classifier step outside Proofsmith's shared budget. Its assertion was updated to require seven remaining agent steps after the one classification call, and an aggregate-budget equality was added. This strengthens fairness rather than removing a failing check.

Final offline suite: **85 passed in 224.15 seconds**. Implementation-preview browser checks passed at desktop and mobile widths. The mobile status badge and code snippet initially overflowed and were fixed; JSON source checks and layout checks then passed.

The complete controlled demo reproduced its historical matrix (all existing tests pass; buggy and backoff fail stress and verifier; both real fixes pass). Full replay reports historical alignment differences in UAF and rounding fixtures after the evaluator corrections. These are retained as differences, not silently overwritten. Clean-clone equality is therefore not yet a passed release gate.

The user approved completing missing dry-runs and the pilot within the existing global cap. Automatic review separately rejected API egress. The user subsequently explicitly authorized the named reports, source excerpts, harnesses and logs to the DeepSeek endpoint within the cap. No paid request was made during the blocked attempts; the authorized continuation then started.
