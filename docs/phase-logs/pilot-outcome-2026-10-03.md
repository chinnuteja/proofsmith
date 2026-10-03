# Pilot outcome — v1

The approved pilot completed all 12 observations. Paid execution stopped afterward. No full experiment or additional paid protocol has started.

Raw fail-to-pass successes: 0. Proofsmith abstained on every pilot case; the baselines either gave up or submitted harnesses that did not pass the hidden fixed-tree evaluation. These are negative pilot outcomes, not a complete benchmark verdict.

Pilot generation cost: $0.948543288. Total recorded spend: $2.594991908. Remaining under the approved global cap: $1.905008092. The old-code estimate for the remaining experiment is $5.857254803, including the safety multiplier. This projection must be remeasured after the repair and does not authorize spending.

The usage audit found 7 final-request token overruns. The original code checked usage after a response. A tested repair now reserves input and completion before requests; its stronger guard is conservative and applies to all systems. The prior protocol, its source commit, verdicts and cost/audit snapshots are retained. A new protocol is prepared offline before any proposed rerun.

Sources: [findings JSON](../../results/pilot_findings.json), [cost JSON](../../results/protocol-history/v1/pilot_cost.json), [usage audit](../../results/protocol-history/v1/pilot_budget_audit.json), [verdicts](../../results/eval/v1), [repair](../repairs/README.md).

The next paid action requires user authorization at the plan's pilot stop. A full comparison remains blocked until a matching completed pilot and clean budget audit exist under the repaired protocol, plus explicit full-run budget approval.
