# Phase 4 log
## Result
GATE 4: PASS

```
== pytest tests/phase0..phase4
....................................................                     [100%]
52 passed, 2 deselected in 357.21s (0:05:57)
== phase-specific checks
instances=12 concurrency=6 lifetime=6 classes={'lifetime': 6, 'race': 4, 'deadlock': 2}
repo https://github.com/cameron314/concurrentqueue 1
repo https://github.com/yhirose/cpp-httplib 3
repo https://github.com/libuv/libuv 4
repo https://github.com/uxlfoundation/oneTBB 3
repo https://github.com/gabime/spdlog 1
200 https://github.com/cameron314/concurrentqueue/issues/288
200 https://github.com/yhirose/cpp-httplib/pull/2232
200 https://github.com/yhirose/cpp-httplib/issues/2431
200 https://github.com/yhirose/cpp-httplib/issues/2492
200 https://github.com/libuv/libuv/issues/2226
200 https://github.com/libuv/libuv/pull/4321
200 https://github.com/libuv/libuv/pull/4980
200 https://github.com/libuv/libuv/pull/5058
200 https://github.com/uxlfoundation/oneTBB/pull/1117
200 https://github.com/uxlfoundation/oneTBB/pull/480
200 https://github.com/uxlfoundation/oneTBB/pull/518
200 https://github.com/gabime/spdlog/issues/1570
== no case-specific prompt tuning
check_no_tuning: OK
== browser gate
/mnt/c/Users/Profile 1/ByteAskEval/site/index.html
serve: OK
BROWSER 4: PASS
GATE 4: PASS
```

## What was built
- proofsmith/datasets/mine.py: blobless clones under ~/psw/repos, the plan's git-log search, size filter (at most 5 non-test source files and 200 changed lines), and curl-based GitHub reads.
- proofsmith/datasets/check.py: schema, separation, fix size, and cached asan_ubsan/tsan builds for both commits. Writes results/trackB_check.json.
- scripts/trackb_mine.sh: rate-limit check, then the miner.
- scripts/trackb_smoke_concurrentqueue.sh: header-only smoke compile for concurrentqueue. The instance stores this path.
- data/trackB/: 12 instances, hidden twins, fix diffs, raw issue JSON, candidates.jsonl, per-repo scan logs, and REJECTED.md (942 rejections).
- proofsmith/report/templates/trackb.html.j2 and site.py: /trackb/ table and class counts. Bug classes stay on this page.
- tests/phase4/: schema, separation, and cached builds.
- scripts/gate_phase4.sh: count and class floors, at most 4 per repo, and HTTP 200 for every issue URL.
- scripts/browser_gate.py: B4.1, B4.2, B4.3.

Accepted classes: deadlock 2, race 4, lifetime 6, ub 0. Concurrency 6. mentions_fix is true on 9. Repos: libuv 4, cpp-httplib 3, oneTBB 3, spdlog 1, concurrentqueue 1. uxlfoundation/oneTBB is the current org (`git ls-remote https://github.com/uxlfoundation/oneTBB HEAD` returned 2143c67c8bc0fff2be474ff15475c746eb6afe22).

## Browser checks
- B4.1: PASS. Twelve rows. Each has an id, a repo, a GitHub issue link, rewritten, mentions-fix, fix size, and four `.pill-pass` cells.
- B4.2: PASS. Summary strip reads deadlock 2, race 4, lifetime 6, ub 0, mentions fix 9, instances 12, with data-source into results/trackB_check.json.
- B4.3: PASS. Row count equals the 12 files in data/trackB/instances/.
- Screenshots: docs/evidence/phase-4/trackb-1280.png, trackb-390.png, B4.1-1280.png, B4.1-390.png, B4.2-1280.png, B4.2-390.png, B4.3-1280.png, B4.3-390.png.
- Layout: the first 1280 shot broke header words, and 390 squeezed the ten columns into a thin strip. Column widths and a mobile card layout fixed that. The repo name breaks after the slash. The gate above is after that fix.
- Layer B: opened three issue links from /trackb/.
  - concurrentqueue-288: title "Endless loop in ImplicitProducer* get_or_add_implicit_producer() · Issue #288 · cameron314/concurrentqueue · GitHub". Body starts "I've been using this nice queue for a while now" and ends "Not sure how to debug this!", matching issue.body. rewritten is false.
  - libuv-2226: title "Threading bug - race condition in uv_async_send · Issue #2226 · libuv/libuv · GitHub". Body includes Version 1.27, the foundationdb steps, and "Am I using libuv correctly?", matching issue.body. rewritten is false.
  - spdlog-1570: title "daily_file_sink has deadlock bug · Issue #1570 · gabime/spdlog". Body is the sink_it / filename() deadlock description and "Happy to fix.", matching issue.body. rewritten is false.

## Spend
- Ledger before: $0.161211 after: $0.161211 phase ceiling: $0.00
- This phase spent $0. No DeepSeek or other LLM call. live_balance was not requested. The figure is the local ledger sum only.

## Deviations from plan
- `gh api` cannot be used unauthenticated with the installed CLI. Evidence, from `gh api rate_limit` in WSL:

```
To get started with GitHub CLI, please run:  gh auth login
Alternatively, populate the GH_TOKEN environment variable with a GitHub API authentication token.
```

Exit code 4. The same unauthenticated REST API works with curl. `curl -sS -D - -o /tmp/proofsmith-rate-body.json -A proofsmith https://api.github.com/rate_limit` returned HTTP 200, `x-ratelimit-limit: 60`, `x-ratelimit-remaining: 30`, `x-ratelimit-reset: 1790927915`. Issue and pull text was fetched with curl. No token was requested.

- A relative `custom_script` is resolved against the Proofsmith repo in proofsmith/oracles/builds.py so the committed recipe is not a machine path. The cache key is still the tree hash, the source-directory hash, and the variant.
- Re-running the full gate rewrote `results/demo/orderd.json` (new ThreadSanitizer tids and `generated_at`) and the phase 0 sanitizer fixtures (new addresses). Those files were restored to `phase-3-done` before the commit. They are not Track B work.

## Open issues for the orchestrator
- httplib-2492 builds with OpenSSL and mbedTLS turned off, because those headers are not installed. The changed SSLClient destructor is not compiled. Both commits still build under asan_ubsan and tsan. The hidden notes record this.
- 9 of 12 instances have mentions_fix true. They are in the accepted set and shown separately on /trackb/.
- redis and rocksdb were mined. Their size-ok commits were not fetched once the 12-instance quota was filled from smaller repos. Reasons are in data/trackB/REJECTED.md. The floor of 10 was met, so no extra repos were added.
