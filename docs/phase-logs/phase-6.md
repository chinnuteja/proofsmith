# Phase 6 — implementation and approved pilot

## User authorization — 2026-10-03

The user explicitly answered: **"Yes, finish dry-runs and pilot within the existing cap"** to the proposal to use the remaining $2.98 of the existing $4.50 ledger cap to complete four missing Phase 5 baseline dry-runs and the twelve-observation pilot, then stop for full-run approval.

This authorizes continuing beyond Phase 5's previously exceeded historical ceiling. It does not rewrite or erase the historical Phase 5 failure, authorize the full experiment, or increase the global cap. The existing live dry-run test also enforces an additional local ceiling of $0.75 for its continuation.

Recorded spend before the continuation: $1.523406932. Remaining under the global cap: $2.976593068. Historical-sample pilot estimate: $1.4810193112, with a safety factor already included. Provisional whole-experiment estimate: $8.5158610394. These are not measured pilot costs.

## Implementation and protocol

The runtime, evaluator, metrics, runner, report, offline replay, and integration implementations are locally available. Protocol populations contain eleven scored Track B instances and twelve Track A instances, across B0, B1 and Proofsmith. httplib-2492 is excluded for the documented build-coverage reason.

The final protocol is re-prepared after pre-observation implementation fixes. Earlier preparation metadata is archived; no generation attempt or protocol observation is discarded. The final protocol and source are committed before the pilot. The full experiment requires a separate user approval and a matching `docs/evaluation-approval.json`; that file has not been created.

## Status

The four missing dry-runs completed: one live plumbing test passed in 954.70 seconds. Their generation cost was $0.123041688. Ledger spend before the pilot: $1.646448620; remaining under the $4.50 cap: $2.853551380. Full outcomes are in `dryrun-continuation-2026-10-03.md`.

Protocol SHA-256: `691c69bb89f54d1e20f74997451394cf58612ec858af004bdb99306a4977cca1`. Implementation and protocol commit: `4fff7ffa35ab9b27b413337fb2a10923c1991382`, created before any pilot attempt. The approved pilot is running. No `GATE 6: PASS` or comparative win has been claimed.

Final offline regression suite: **85 passed in 224.15 seconds**. Desktop and mobile implementation-preview browser checks passed with source values verified against JSON and all protocol instance links returning HTTP 200.

Automatic approval review blocked the paid command twice. The user then explicitly answered: **"Yes, I authorize sending those reports, source excerpts, harnesses and logs to https://api.deepseek.com within the $4.50 cap"**, in response to the question naming `deepseek-v4-pro`, visible C/C++ excerpts, bug reports, generated harnesses and compile/test logs. The authorized dry-run continuation is now running. The cap and full-run stop remain in force.

The approved cap is guarded before each model request using a cache-miss input and maximum-completion cost reservation. A cap stop can leave the pilot incomplete; missing pairs remain missing and no estimate is substituted for an observation.
