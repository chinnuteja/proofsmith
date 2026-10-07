# Five-case ByteAsk acceptance comparison

This is a small test of whether a frozen Proofsmith check catches incorrect patches that ByteAsk says are ready. It does not test whether Proofsmith has a better model. The real five-case collection is complete; see `docs/byteask-live-comparison.md` and `experiments/byteask-comparison/live-v1-score/index.html` for the scored outcome. The earlier DeepSeek experiment is separate.

The run uses the existing included ByteAsk allowance with **$0 additional spending**. Do not purchase a subscription, top up credits, upgrade, or fall back to a paid provider. The signed-in account reported an existing Pro allowance, zero extra/prepaid credit, and adequate remaining quota. The collector checked usage before and after each case. Account credentials and the ByteAsk binary are excluded from the kit.

## Cases and controls

The five cases are new authored C++ boundary problems: unsigned quota overflow, wire-frame length truncation, cache expiry equality, queue-prefix consumption, and signed notional width. They differ from the existing arithmetic installation fixture and orderd/Catch2 demonstrations. They are synthetic cases, not an upstream benchmark, and are not guaranteed novel relative to a model's training data.

Each case has an original source tree, a normal smoke test, a supplied regression check, and an independent evaluator that uses additional inputs and a reference calculation or model. The original, correct fix, and partial fix are authored controls. These controls check the benchmark machinery and **cannot enter ByteAsk model scores**.

Preparation compiles everything with the real C++ toolchain, qualifies each check with ten original runs, and gates every control with twenty original and twenty candidate runs. Independent evaluators must reject the original and partial fix and accept the correct control. All controls must pass the ordinary smoke test. Compiler/run logs and portable gate receipts are retained. These results measure these checks and fixtures; their finite coverage does not establish general correctness.

## Paired model comparison

Use one actual ByteAsk-generated candidate per case, five model runs total. The baseline is ByteAsk's own declared acceptance of that candidate. The augmented decision accepts that same candidate only when ByteAsk accepts it **and** the independently executed frozen Proofsmith gate returns VERIFIED. This isolates the effect of adding a final gate without changing the repair model, patch, or repair budget. It does not evaluate MCP-guided repair or improved repair success.

Pin one model, provider, CLI binary, and account/tool tier before starting. Use a new isolated workspace per case, no prior transcripts or repair attempts, a maximum of twenty turns and ten minutes per case. Allow ByteAsk its available native sanitizer/debugging tools and normal shell build/test tools. Both decisions share the exact same repair trace. The extra gate runtime must be reported as overhead, not treated as free latency.

The agent-visible workspace contains only the original source and the supplied regression check plus `proofsmith_check.h`. The agent may read and run the supplied check; the evaluator always uses its external frozen copy. Do not expose the authored fixes, independent judge, previous control receipts, or other cases. A workspace-write sandbox alone allows reads outside the workspace, and ByteAsk's native tools run outside that shell sandbox. The separate live collector uses an outer bubblewrap filesystem allowlist that hides the experiment and Proofsmith work/cache directories while preserving the available native tools. The offline script does not launch models.

Ask the agent to fix the issue, keep the API and normal behavior, run appropriate tests, name every tool and quote its key output, and end with `BYTEASK_ACCEPTED` only if it considers the patch ready, otherwise `BYTEASK_UNRESOLVED`. Do not constrain the investigation with an output schema: ByteAsk's [headless documentation](https://docs.byteask.ai/docs/headless) describes investigation bias and provider limitations for schema output. Parse only the final marker, never a quoted marker elsewhere in the trace. Missing or contradictory markers are unresolved. Retain JSONL, stderr, final response, candidate snapshot/diff, wall time, available account-usage evidence, and exact execution settings. Native tool calls may be absent from JSONL in this CLI version; that does not prove that the tool was not used.

One attempt per case. Timeouts, errors and quota exhaustion are recorded; no silent retries or replacement cases. The five cases stay selected even when a case is inconvenient. Model/provider settings must be frozen separately before collecting candidates; the checked-in protocol deliberately leaves them unset because account availability is unknown.

## Scoring and stopping

Primary measurement: incorrect candidates accepted, judged using the independent evaluator. Secondary measurements: correct candidates accepted, unresolved candidates, model time, gate overhead and actual account usage. Passing a frozen check is not itself the independent definition of correctness. Compile or evaluator failures are unresolved and block a winning pilot claim.

A positive pilot signal requires all five real observations, fewer incorrect acceptances, no reduction in correct acceptances, and at least one correct candidate accepted. Rejecting everything is insufficient. If ByteAsk's five fixes are already correct, report **no demonstrated advantage**. If the gate rejects a correct fix, report that too. Positive results require a separate held-out confirmation set before any broad superiority claim. Otherwise stop expanding the benchmark and share the product with the honest outcome.

The offline scorer requires real-model origin labels, retained transcript hashes, the matching protocol identity, and one pinned model/provider. Scripted localhost integration and authored controls are excluded. These hashes verify retained bytes; they do not authenticate authorship or certify the provenance of externally supplied observations. A real run needs an audited collector as well.

## Offline reproduction

From the checkout in the configured WSL Python environment:

```powershell
.\scripts\ws.ps1 scripts/byteask_comparison.sh prepare --out /tmp/proofsmith-byteask-new
.\scripts\ws.ps1 scripts/check_byteask_comparison.sh
.\scripts\ws.ps1 scripts/comparison_preflight.sh
```

Use a new output path for preparation. The prepared version is `experiments/byteask-comparison/v1`; open its `index.html`, `offline-results.json`, and `protocol.json`. It keeps the previously frozen DeepSeek v5 protocol unchanged.

After genuine candidates have been collected, score a JSON list using:

```bash
python scripts/byteask_comparison.py score --experiment experiments/byteask-comparison/v1 \
  --observations real-observations.json --out /tmp/byteask-real-score
```

Each observation requires `case_id`, `origin=byteask_model`, `candidate_path`, `claimed_status=ACCEPTED|UNRESOLVED`, `model`, `provider`, `protocol_sha256`, `transcript_path`, `transcript_sha256`, `wall_s`, and `account_usage`. Missing usage may be null and must be described as unavailable. The pending JSON is an explicit non-run template and is refused by the scorer.

For sign-in, use your existing ByteAsk installation or this project's isolated WSL CLI:

```powershell
.\scripts\ws.ps1 scripts/byteask_local.sh login --email YOUR_EMAIL
```

Complete authentication yourself. Do not paste passwords, API keys or access tokens into chat. The retained collection used `gpt-5.4` through the official ByteAsk managed provider, pinned in `live-v1/execution-lock.json` before model requests. The fifteen offline controls must not be described as model results. To reproduce the retained real candidate scores without an account or another model run, use `bash scripts/rescore_byteask_comparison.sh --out /tmp/proofsmith-real-recheck` with a fresh output path.
