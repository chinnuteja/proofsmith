# Frozen evaluation protocol

Protocol ID: `v2`. SHA-256: `d254e46348c3a417f83f4f43902338aa1c20e77cb1110c276cd578baa498c395`.
The complete population, execution order, constants, budgets, source hashes and exclusions are in [protocol.json](protocol.json).
Frozen at `2026-10-03T13:48:23.414832+00:00` before new observations. Historical exploratory samples are retained separately and cannot enter this protocol's metrics.

Model: `deepseek-v4-pro`, temperature `0`, randomized system order with seed `20261001`.
Shared budget: `50` steps, `500000` total prompt plus completion tokens, `1800` seconds. Classifier calls count toward Proofsmith's budget. All systems receive the same tools, model, and budget.

Token accounting: Reserve serialized UTF-8 input plus chat framing before every request, then clamp completion to the remaining shared budget. This conservative bound may stop before actual tokens are exhausted.

Runtime acceptance requires stable eligible evidence in 8 of 10 runs.
Evaluation raw F→P requires successful builds on both trees, at least 16 buggy failures in 20 runs and 0 fixed failures. Timeout per run: 60 seconds.
Alignment strict means a failure frame or executed coverage region overlaps a function actually changed by the fix; relaxed means a changed source file is hit. Diff context alone does not change a function. Unavailable coverage is unknown. Alignment does not alter raw F→P.

One generation attempt per pair. Interrupted attempts remain auditable and are not silently regenerated. Per-pair infrastructure errors are stored. An explicit infrastructure retry requires a separate logged decision. Existing verdicts are immutable. Only the evaluator sees the hidden fixed code.

## Metrics and kill criteria

Report raw, aligned strict and aligned relaxed F→P counts and percentages with Wilson 95% intervals; unknown alignment; successful oracles; median cost and wall time; and fixed-tree flake rate (1 ≤ fixed failures < evaluation run count, divided by submitted or accepted bundles).
Abstention precision is Proofsmith abstentions where B1 is also not F→P divided by paired Proofsmith abstentions. Missing B1 observations do not count as correct abstentions.
Paired exact two-sided McNemar compares aligned strict success against B1, with discordant counts b and c and `min(1, 2 * sum(comb(b+c, i) for i in range(min(b,c)+1)) / 2**(b+c))`.

- Track B verdict `PASS` if `aligned_strict_pct(proofsmith) − aligned_strict_pct(b1) ≥ 20` points, else `KILL_OR_RETHINK`.
- Track A verdict `OK` if `raw_pct(proofsmith) ≥ raw_pct(b1) − 5`, else `RESTRICT_TO_LIFETIME_CONCURRENCY`.

An incomplete experiment reports `INCOMPLETE`. Unresolved alignment reports `ALIGNMENT_UNRESOLVED`; it cannot support a success claim. No missing observation is filled with a fabricated failure or success.

## Pilot and approval

Pilot: two Track B and two Track A instances, all three systems. `results/pilot_cost.json` records per-system mean and maximum cost and wall time, with a full-run projection using a 1.3 safety multiplier. Stop after the pilot. A full run requires human budget approval recorded in `docs/phase-logs/phase-6.md` and `docs/evaluation-approval.json`, tied to this protocol's SHA-256. Current preparation grants no new spending approval.

## Populations

Track B: `concurrentqueue-288`, `httplib-2232`, `httplib-2431`, `libuv-2226`, `libuv-4321`, `libuv-4980`, `libuv-5058`, `onetbb-1117`, `onetbb-480`, `onetbb-518`, `spdlog-1570`.

Pilot B: `concurrentqueue-288`, `httplib-2232`.

Track A: `Catch2-2288`, `fmt-3569`, `fmt-3713`, `fmt-3734`, `fmt-4057`, `fmt-4310`, `httplib-1765`, `json-1769`, `json-2332`, `json-4537`, `json-708`, `json-807`.

Pilot A: `Catch2-2288`, `fmt-3569`.

Excluded: `httplib-2492`. See `data/trackB/EXCLUDED.md`.

## Execution order

1. B/concurrentqueue-288/proofsmith
2. B/concurrentqueue-288/b1
3. B/concurrentqueue-288/b0
4. B/httplib-2232/b0
5. B/httplib-2232/proofsmith
6. B/httplib-2232/b1
7. B/httplib-2431/b1
8. B/httplib-2431/proofsmith
9. B/httplib-2431/b0
10. B/libuv-2226/b1
11. B/libuv-2226/proofsmith
12. B/libuv-2226/b0
13. B/libuv-4321/b1
14. B/libuv-4321/b0
15. B/libuv-4321/proofsmith
16. B/libuv-4980/b1
17. B/libuv-4980/proofsmith
18. B/libuv-4980/b0
19. B/libuv-5058/b0
20. B/libuv-5058/proofsmith
21. B/libuv-5058/b1
22. B/onetbb-1117/proofsmith
23. B/onetbb-1117/b1
24. B/onetbb-1117/b0
25. B/onetbb-480/proofsmith
26. B/onetbb-480/b1
27. B/onetbb-480/b0
28. B/onetbb-518/b0
29. B/onetbb-518/proofsmith
30. B/onetbb-518/b1
31. B/spdlog-1570/proofsmith
32. B/spdlog-1570/b1
33. B/spdlog-1570/b0
34. A/Catch2-2288/b1
35. A/Catch2-2288/proofsmith
36. A/Catch2-2288/b0
37. A/fmt-3569/b1
38. A/fmt-3569/b0
39. A/fmt-3569/proofsmith
40. A/fmt-3713/b0
41. A/fmt-3713/b1
42. A/fmt-3713/proofsmith
43. A/fmt-3734/b0
44. A/fmt-3734/proofsmith
45. A/fmt-3734/b1
46. A/fmt-4057/proofsmith
47. A/fmt-4057/b1
48. A/fmt-4057/b0
49. A/fmt-4310/proofsmith
50. A/fmt-4310/b0
51. A/fmt-4310/b1
52. A/httplib-1765/b0
53. A/httplib-1765/proofsmith
54. A/httplib-1765/b1
55. A/json-1769/b0
56. A/json-1769/b1
57. A/json-1769/proofsmith
58. A/json-2332/b1
59. A/json-2332/proofsmith
60. A/json-2332/b0
61. A/json-4537/b0
62. A/json-4537/b1
63. A/json-4537/proofsmith
64. A/json-708/proofsmith
65. A/json-708/b0
66. A/json-708/b1
67. A/json-807/proofsmith
68. A/json-807/b0
69. A/json-807/b1
