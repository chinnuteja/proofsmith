# Proofsmith verification tool

Freeze a check before patching. Reproduce its failure on the original code. Replay the exact check against a proposed fix. Keep a portable receipt, compiler logs, every run's raw output, and source and verifier identities.

This tool runs offline with Linux or WSL, clang/LLVM, CMake and bubblewrap. It makes no model requests. Model-generated verifier quality remains a separate, incomplete experiment.

## Try it

```bash
python -m pip install -e '.[dev,mcp]'
proofsmith demo gate
proofsmith demo upstream
```

The commands print evidence directories. Open `index.html` for the controlled demo, or `fixed/index.html` for the upstream example. All three order-book patches pass the existing tests; the frozen TSan check rejects the timing workaround and accepts both lock fixes. Each gate repeats twenty runs per tree. This is a supplied reference check, not a model-generated benchmark win.

The upstream example requires the cached pinned Catch2 dataset source and never fetches it. It checks whether a `const Approx` factory is callable with a `double`, through its source header. The original code fails and the recorded upstream fix passes. This is a supplied type-level API check, not runtime coverage of the changed function. It stays outside the comparative scores. The verifier is frozen before the recorded fix is applied.

## Use your own check

An instance JSON supplies the existing BuildRecipe. A harness directory contains `build.sh`, which produces `$PS_OUT/harness`, plus its C/C++ source. Use `PS_CHECK` for explicit assertions or the configured sanitizers for runtime faults. The check may not change application source or its frozen files during execution.

```bash
proofsmith seal --repo /work/original --harness /work/check \
  --instance /work/instance.json --oracle asan_ubsan --out /work/sealed

# Retain this identity before the coding agent patches anything.
proofsmith bundle-id --bundle /work/sealed/bundle

proofsmith gate --bundle /work/sealed/bundle \
  --baseline /work/original --candidate /work/proposed-fix \
  --instance /work/instance.json --expect-bundle-id <pre-patch-sha256> \
  --out /work/patch-evidence
```

`seal` requires stable eligible evidence in at least eight of ten runs. Sanitizer evidence must include application frames. The bundle binds the original source and build recipe. The gate requires the trusted pre-patch identity, matching source and recipe, at least sixteen matching original failures in twenty runs, and no candidate failures. Both source trees run on disposable copies. Outputs must be new directories separate from the inputs; source symlinks are currently unsupported.

| Exit | Status | Meaning |
|---|---|---|
| 0 | VERIFIED | Original target reproduced; candidate passed every run of this check. |
| 1 | REJECTED | The same target still fires on the proposed fix. |
| 2 | INCONCLUSIVE | Build failure, unexpected failure, weak reproduction, changed source, or verifier mismatch. |

Use the exit code in CI. A compiler error never counts as a reproduced bug or verified fix. An unrelated crash cannot earn a green check. The gate checks source and harness integrity after execution, so a self-modifying check cannot qualify or verify a patch.

## Verify and share receipts

Receipts include `receipt.json`, an independent HTML report, the frozen bundle, raw logs, and `manifest.json`. Copy the whole directory to preserve relative links.

```bash
proofsmith evidence-check /work/patch-evidence
proofsmith evidence-check /work/patch-evidence --expect-manifest <trusted-manifest-sha256>
```

Retain the manifest digest separately when sharing evidence. Hashes detect changes relative to a trusted identity; they are not signatures and do not identify an author. A receipt records finite executions, not correctness on every input. The gate does not establish changed-function alignment or comparative performance.

## Use over MCP

```json
{"mcpServers":{"proofsmith":{"command":"/path/to/venv/bin/proofsmith","args":["mcp"]}}}
```

`make_verifier` is the optional metered generator and returns the bundle identity. Keep a pristine baseline, let the agent create a separate candidate checkout, then call `check_patch(bundle_path, baseline_path, candidate_path, expected_bundle_id)`. It returns the verdict, measurements, and JSON/HTML receipt paths. The simpler `verify` tool also replays on a disposable copy.

The official SDK stdio connection is tested locally. A signed-in end-to-end ByteAsk run remains outstanding.

## Show it in ninety seconds

1. Show the timing workaround's passing existing tests and REJECTED receipt.
2. Expand its raw lock-order-inversion report.
3. Show the same pinned check on a lock fix: original 20/20 failures, candidate 0/20.
4. Show the real Catch2 example; state that its check is supplied.
5. Run evidence-check and show the JSON receipt and MCP contract.

The concrete value is a reusable pre-patch check with evidence reviewers can inspect.
