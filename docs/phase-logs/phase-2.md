# Phase 2 log

## Result

GATE 2: PASS

```
== pytest tests/phase0..phase2
......................................                                   [100%]
38 passed, 1 deselected in 258.76s (0:04:18)
== phase-specific checks
.                                                                        [100%]
1 passed in 5.27s
spent: $0.001285
cap: $4.50
remaining: $4.498715
balance: $4.98
== no case-specific prompt tuning
check_no_tuning: OK
== browser gate
/mnt/c/Users/Profile 1/ByteAskEval/site/index.html
serve: OK
BROWSER 2: PASS
GATE 2: PASS
```

## What was built

- `config/pricing.json`: DeepSeek peak prices, source URL, fetch date 2026-10-01
- `proofsmith/llm.py`: `LLMClient`, `FakeLLM`, `Usage`, `ToolCall`, `LLMResponse`
- `proofsmith/ledger.py`: append-only `runs/ledger.jsonl`, `ensure_budget`, `proofsmith ledger status`
- `proofsmith/sandbox.py`: copy without `.git`, one snapshot commit, `unshare -rn` with loopback up
- `proofsmith/agent/tools.py`: `run_shell`, `read_file`, `write_file`, `list_dir`, `build_variant`, `run_harness`, `finish`, `abstain`
- `proofsmith/agent/loop.py`: shared `run_agent` with the 50-step / 500000-token / 1800s budget and trajectory JSONL
- `proofsmith/agent/smoke.py`: `proofsmith agent smoke` on `deepseek-flash`
- `proofsmith/report/templates/runs.html.j2`, `run.html.j2`: run index and per-step viewer
- `proofsmith/report/site.py`: copies each `summary.json` to `site/data/runs/<run_id>.json`
- `scripts/gate_phase2.sh`: runs the live smoke once, then `proofsmith ledger status`
- `scripts/browser_gate.py`: checks B2.1–B2.5
- `tests/phase2/`: ledger, fake client, sandbox, tools, loop, live smoke

## Browser checks

- B2.1: PASS. `/runs/` lists `live-smoke` with status `finished`.
- B2.2: PASS. The run page shows 3 steps. Each tool call shows its name and arguments. A tool-output block expands.
- B2.3: PASS. Token and cost totals match `runs/live-smoke/summary.json`.
- B2.4: PASS. Budget bar `aria-valuenow` is the token total and `aria-valuemax` is 500000.
- B2.5: PASS. Page source has no string starting with `sk-`.
- Screenshots: `docs/evidence/phase-2/runs-1280.png`, `docs/evidence/phase-2/runs-390.png`, `docs/evidence/phase-2/run-1280.png`, `docs/evidence/phase-2/run-390.png`, plus `B2.1`–`B2.5` at both widths.
- Layer B: opened `http://127.0.0.1:8765/runs/` in the Cursor browser. The index shows one finished smoke run. The run page reads as three steps without opening JSON: `list_dir`, then `run_shell` (a grep for mutex in the order-book sources), then `finish` whose summary names `book_mtx_` and `risk_mtx_`. Expanding the shell output is a normal disclosure. The budget bar is a thin sliver because 4046 tokens is a small fraction of 500000; the numbers next to it are the readable part.

## Spend

- Ledger before: $0.000000  after: $0.001285  phase ceiling: $0.10
- Cap: $4.50. Remaining after the phase: $4.498715.
- Live balance from `GET https://api.deepseek.com/user/balance`: $4.98 (shown to the cent; it did not move visibly for this sub-cent spend).
- Two `deepseek-flash` smokes ran (one while checking the loop, one inside the gate). The gate smoke cost $0.000498. Neither call printed the API key. The live test asserts the key prefix is absent from the trajectory.

## reasoning_content

Do not resend it. `RESEND_REASONING` in `proofsmith/agent/loop.py` stays false.

The gate smoke's trajectory has `reasoning_content` on the model responses (`response_had_reasoning True`) and does not put that field on later requests (`request_resent_reasoning False`). The follow-up turns still returned tool calls and the run finished. The API did not require `reasoning_content` to be sent back.

## Deviations from plan

- Pricing page lists two rates. Fetched `https://api-docs.deepseek.com/quick_start/pricing` on 2026-10-01. Peak and off-peak are both published; off-peak is half of peak (for example flash output is $1.20 peak and $0.60 off-peak per 1M tokens; `deepseek-v4-pro` output is $3.96 peak and $1.98 off-peak). The plan's `pricing.json` shape has one number per field. The file stores the peak rate for each field, which is the higher listed price, so the ledger does not undercount. Unknown or null prices use the highest listed number, $3.96 per 1M tokens. No price was invented.
- `finish` and `abstain` are two tool schemas. The plan's seventh bullet names both, and the model has to be able to call either one.

## Open issues for the orchestrator

- Confirm peak rates in `config/pricing.json` are the intended ledger price. Off-peak is also on the official page and was not stored.
