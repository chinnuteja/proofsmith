# Completed live ByteAsk comparison

**Five real ByteAsk repairs tested. All five passed the independent evaluators and Proofsmith gates. No advantage over ByteAsk was demonstrated. Additional purchases: $0.**

Open `experiments/byteask-comparison/live-v1-score/index.html` for the recorded results, candidate diffs, final responses, CLI transcripts and gate receipts. The installable evaluation kit is `artifacts/proofsmith-byteask-evaluation-kit.zip`. It includes the unchanged Proofsmith 0.2.0 wheel, source, frozen checks, independent evaluators and offline reproduction scripts. It has not been sent or published.

| Measurement | ByteAsk | ByteAsk + frozen gate |
|---|---:|---:|
| Incorrect candidates accepted | 0 | 0 |
| Correct candidates accepted | 5 | 5 |
| Unresolved cases | 0 | 0 |

The five cases were quota overflow, frame-length truncation, cache-expiry equality, queue-prefix consumption and signed notional width. The independent evaluators exercised 5,419 checks, with zero failures on the real candidates. Every frozen gate reproduced the original failure in 20/20 runs and observed zero failures in 20 candidate runs. These finite executions do not prove correctness on every input.

ByteAsk model/CLI wall time totaled 236.85 seconds. The additional frozen gates took 135.12 seconds (about 27 seconds per case), including independent original/candidate builds and repeated runs. The gate time is additional latency. Independent evaluator time is separate from these totals. All runs used the same pinned `gpt-5.4` model and official ByteAsk provider, one attempt per selected case, at most twenty turns and ten minutes per case. No retries, replacement cases, model fallback or altered checks were used.

The account had an existing Pro allowance. The gateway reported usage moving from 0% to 3% of the five-hour window and 0% to 1% of the weekly window. Extra/prepaid balance and extra spending remained zero. No subscription, top-up or purchase was made. These rounded usage percentages are not per-case dollar costs. The previous DeepSeek ledger and frozen v5 protocol remain unchanged.

The CLI used real shell compiler checks and native `cpp_sanitize` on several cases, reporting clean ASan/UBSan runs. Attempts to use `cpp_check`, `cpp_tidy` and `cpp_nav` reported missing `cppcheck`, `clang-tidy` and `clangd` dependencies. Those tools were not successfully exercised. The model still used the available native sanitizer/build tools and normal shell tools; this is not a claim about ByteAsk with every optional tool installed. Full final responses and stderr retain these limitations. Native-tool details can be absent from this CLI's JSONL.

The collector's outer bubblewrap filesystem allowlist hid the main repository, authored fixes, independent evaluators and host home. Only the candidate workspace, private ephemeral ByteAsk profile, CLI binaries and system toolchain were mounted. The actual binary and compiler passed the access probe before requests. The agent received the issue, original C++ files, supplied check and runtime header. The hidden judge and authored fixes were excluded from the model payload. A separately frozen execution lock records the collector/binary/protocol identities, prompt, case order and limits. Credentials and the private profile are excluded from evidence.

Automatic review rejected the earlier launch before execution for missing explicit payload-and-destination consent. The user then replied “do it” directly to the exact transfer request for the five fixtures, supplied checks, task descriptions and tool output to `https://code.byteask.ai/byteask/v1`, using `gpt-5.4` within the existing allowance and $0 additional spending. That authorization was recorded in `results/byteask-transfer-authorization.json`; the subsequent reviewed launch ran successfully.

To compile and evaluate the retained candidates afresh on Linux/WSL, install the wheel and toolchain as described in `docs/byteask-integration.md`, then:

```bash
bash scripts/rescore_byteask_comparison.sh --out /tmp/proofsmith-real-recheck
```

Use a new output path. This makes no model requests and requires no ByteAsk account. Original collection records retain the original absolute paths; the rescorer rebases only a temporary input and checks retained transcript and execution-lock hashes. It compares fresh independent evaluations and frozen gate decisions with the recorded results. Hashes bind retained bytes, not authorship.

The fifteen separate authored controls still show ten incorrect controls refused and five correct controls approved. They validate the machinery and are excluded from model scores. The real pilot evaluates acceptance of the same ByteAsk candidates, not MCP-guided repair, a better model, automatic verifier generation, broad superiority or vulnerability discovery. The older automatic-verifier pilot did not establish a generation-quality win.

The bounded comparison is complete. Because ByteAsk's baseline was already correct on every selected case, stop expanding this pilot and present the product with the honest outcome. The useful deliverable is a reusable C++ patch gate with frozen checks, portable receipts and CLI/MCP/CI integration. Read `docs/byteask-comparison.md` for the preselected methodology. The `v1` report remains the historical offline-preparation snapshot and links to the completed live report.
