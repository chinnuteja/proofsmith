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

Phase 6's dry-run plumbing check and approved v1 pilot are complete. The protocol and implementation were committed at `4fff7ff` before its twelve observations. Pilot cost was $0.948543288; no run achieved raw fail-to-pass. Seven runs exceeded the nominal token budget. The repaired guard, protocol versioning and audit blocker passed 35 offline checks, and v2 is prepared without starting paid observations. Total recorded spend is $2.594991908, leaving $1.905008092 under the cap. The old-code remaining-experiment estimate is $5.8572548034; it must be remeasured after repair. See the pilot outcome log and archived v1 reports. No full experiment is approved or running.

Clean-clone offline reproduction passed at commit `5488133`: the controlled demo and all **38 frozen verifier outcomes** matched. The clone started clean, had no `.env` file, used no model key, and reused the installed WSL toolchain and cached pinned upstream mirrors. The first clone exposed one uncommitted protocol input; that exact read-only build-monitor script was included, and every recorded input was verified against its committed Git blob before the successful retry. Receipt: `results/reproduction_receipt.json`.

The four erroneous historical alignment references were corrected from the audited real replay, with originals archived byte for byte and all raw outcomes preserved. Phase 7 is still not send-ready: a full valid experiment and qualifying winning worked cases remain absent. The generated outreach remains a draft.

Phase 8 remains conditional on Track B PASS and separately approved spend. No patch-correctness catch count has been claimed.

Phase 9's local stdio integration is tested. A signed-in end-to-end run with the actual headless product, and a publication/license review of the benchmark package, remain outstanding. No message has been sent and no package has been published.

## Offline verification tool — 2026-10-04

Implemented `seal`, `bundle-id`, `gate`, and `evidence-check`, plus the MCP `check_patch` tool. Gates require a trusted pre-patch bundle identity, the original source snapshot, the same build recipe, stable matching original failures, and a clean candidate. Unrelated failures, changed source or harness files, and build failures cannot produce VERIFIED. Input checkouts stay untouched. Evidence packages include JSON/HTML receipts, raw logs, frozen harness bytes and a manifest. Trusted manifest digests can be checked independently.

The controlled order-book demonstration rejected a timing workaround despite passing existing tests: original and candidate target failures were both 20/20. Two lock fixes passed with original target failures 20/20 and candidate failures 0/20. The real Catch2 API development example also recorded 20/20 original failures and 0/20 fixed failures. It checks a type-level API property through the source header and does not establish runtime changed-function alignment. All checks are supplied; none enters the model comparison. Evidence is in `results/tool-demo/`; usage and a short demo sequence are in `docs/verification-tool.md`.

The broader offline set initially passed 114 checks with one failure in a test that required a real API key. That test now supplies and deliberately logs a synthetic secret to test redaction. Eighteen focused checks passed after the repair and final safeguards; the final official-SDK MCP round trip also passed. These checks include real C++ runs. No additional model calls or paid spend occurred.

Unrun protocol v2 is archived; current implementation hashes are frozen as v4 with no paid observations. The complete comparison, model-generated winning cases, signed-in ByteAsk run, and publication remain incomplete. The earlier clean-clone receipt describes its recorded commit, not this new tool release.

The new tool release also passed a clean-clone check at commit a7229e6: protocol v4 validated, all seven evidence-package manifests matched, and the supplied upstream Catch2 check reproduced original failures 20/20 and fixed failures 0/20. The clone had no .env or model key and reused the existing WSL toolchain and cached pinned upstream mirrors. Receipt: results/tool-reproduction.json. Desktop and mobile report checks passed, and the portable local ZIP passed its integrity check. Nothing was published or sent.
