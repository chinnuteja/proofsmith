# Offline verification tool — 2026-10-04

The continuation finishes an offline patch verification tool while retaining the first pilot's negative result. It adds qualification and freezing of supplied checks, mandatory pre-patch identity pinning, original-source and build-recipe checks, source-preserving replay, target-signature matching, conservative inconclusive outcomes, and portable evidence receipts. It exposes the gate over the official MCP SDK and keeps single-tree MCP replay on disposable copies.

Two independent demonstrations are recorded in `results/tool-demo/`: a controlled TSan lock-order example that rejects a timing workaround even when existing tests pass, and a supplied type-level consumer check for the real pinned Catch2 const-API issue. The latter uses the source API header rather than the stale amalgamated header used by the earlier baseline. The verifier is frozen before the upstream patch is applied. No historical comparison verdict is changed, no model-generated win is claimed, and no runtime alignment credit is assigned to the type-level check.

Tests:

- Initial new gate and MCP checks: 12 passed in 255.61 seconds.
- Broad offline set: 114 passed, one failed in 534.71 seconds. The failure was a test requiring an API key even in offline mode.
- Final loop and gate checks: 17 passed, one intentionally deselected slow demo in 4.89 seconds. The repaired redaction test uses a unique synthetic key and checks its removal from logs.
- Final official-SDK MCP round trip, with gate receipt provenance: one passed in 116.57 seconds.

The final gate checks exercise tampered metadata, changed baseline, unpinned identity, changed recipe, source links, unrelated crashes, weak reproduction, compiler failure, self-modifying source, output overlap, altered logs, and replaced manifests. Real controlled-demo outcomes are measured by the broad run. Raw evidence and reports are preserved; report rendering changes retain measured outcomes.

The offline v3 protocol archives unrun v2 and hashes current code. The pilot scope and all previous results remain preserved. No additional API spend or full experiment occurs in this continuation. CLI ByteAsk is not available on the Windows path; a real signed-in product run remains outstanding.
