# Pilot-discovered token limit repair

The first frozen-protocol Proofsmith observation consumed 528,942 prompt plus completion tokens against the nominal 500,000 limit. The original loop checks usage after a model response and can overshoot on its last request, including a terminal response. This is separate from the dollar cap, which is reserved before paid requests.

`token-budget.patch` contains the token repair and regressions. It was first prepared in an isolated copy without changing the active experiment. The candidate checks passed: **21 passed in 80.25 seconds**. After all twelve v1 observations completed and paid execution stopped, the patch was applied. The applied repair, protocol versioning, full-run audit guard and report checks then passed **35 tests in 66.34 seconds**.

The repair reserves a conservative upper bound for input (serialized UTF-8 messages and tools plus chat framing), then reduces the completion allowance to fit the remaining token budget. It stops before a request whose input cannot fit. The same guard applies to both baselines and Proofsmith's oracle loop; classifier requests and retries also reserve the shared budget. A provider-reported overrun cannot execute the terminal tool or enter acceptance judging.

The bound is deliberately conservative and can stop before the actual token allowance is exhausted. That tradeoff must be stated in a new protocol. The fixture fairness test's token allowance is increased only so its schema and step comparisons can run under the stronger guard. The tiny-budget pipeline test now requires zero requests, rather than permitting an overrun.

Protocol v2 is now prepared offline with the same instances, model and ordering, and explicit conservative token accounting. Version changes archive completed prior protocol metadata and refuse unresolved attempts or reused IDs. Original v1 verdicts and its summary, cost and budget audit are retained. The results site exposes v1 separately from v2's pending observations.

The full-run guard also requires a matching completed pilot and complete budget audit without violations, in addition to human budget approval. No v2 pilot or full run has started. The required paid stop remains in force. The old pilot can inform provisional cost planning; its projection must be remeasured under the repaired code before advancing a full comparative experiment.
