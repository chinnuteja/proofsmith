# Proofsmith

Freeze a C++ regression check before repair. Test the original and candidate independently. Ship the decision with evidence a reviewer can replay.

Proofsmith is a working verification companion with CLI, MCP and CI interfaces. It qualifies supplied checks, binds their identities to the original source and build recipe, and returns **VERIFIED**, **REJECTED** or **INCONCLUSIVE**, with HTML/JSON receipts, raw compiler/run logs and integrity manifests. Source trees remain untouched.

**[Open the product overview](https://chinnuteja.github.io/proofsmith/overview/)** · [ByteAsk case study](https://chinnuteja.github.io/proofsmith/) · **[Download the installable evaluation kit](artifacts/proofsmith-byteask-evaluation-kit.zip)** · [Integration guide](docs/byteask-integration.md)

## What the real ByteAsk run showed

Five authored C++ boundary cases, one real repair attempt per case, `gpt-5.4` through the official ByteAsk provider. The agent saw the original source, issue and supplied regression; authored fixes and independent evaluators were hidden during repair.

| Acceptance decision | Correct candidates accepted | Incorrect candidates accepted |
|---|---:|---:|
| ByteAsk | 5 | 0 |
| Same ByteAsk repairs + Proofsmith gate | 5 | 0 |

All five candidates passed 5,419 independent evaluator checks. Every gate reproduced the original failure in 20/20 runs and observed 0/20 candidate failures. **No advantage over ByteAsk was demonstrated in this pilot.** Five synthetic cases cannot establish broad superiority or general patch correctness.

Repair/model wall time was 236.85 seconds; the additional gates took 135.12 seconds. Existing included allowance was used with $0 additional purchases. Optional cppcheck, clang-tidy and clangd dependencies were missing; successful native sanitizer and shell build checks, tool errors and exact execution settings are retained. [Run notes and limitations](docs/byteask-live-comparison.md).

The separate fifteen authored controls validate refusal behavior: ten incorrect controls passed ordinary smoke tests but were refused by the frozen gates; five correct controls were accepted. They are **excluded from model scores**. Inspect [the live result data](experiments/byteask-comparison/live-v1-score/results.json), [patches and traces](experiments/byteask-comparison/live-v1), and [the frozen methodology](docs/byteask-comparison.md).

## Install and reproduce without an account

Use Linux/WSL, Python 3.12+, clang/LLVM, CMake and bubblewrap. In a virtual environment:

```bash
python -m pip install 'artifacts/proofsmith-0.2.0-py3-none-any.whl[mcp]'
bash scripts/rescore_byteask_comparison.sh --out /tmp/proofsmith-real-recheck
```

Choose a new output path. This rebuilds the retained candidates, runs the independent evaluators and frozen gates, and checks the decisions against recorded results. It makes no model requests and requires no ByteAsk credentials. The shipped ZIP passed fresh-extraction reproduction with the existing Linux toolchain and Python dependencies; all five real scores and 19 policy tests reproduced. [Reproduction receipt](results/byteask-comparison-reproduction.json).

For development and a small real compiler/CI installation check:

```bash
python -m pip install -e '.[dev,mcp]'
bash scripts/ci_gate.sh /tmp/proofsmith-install-check
```

Use [the verification guide](docs/verification-tool.md) for your own supplied check and original/candidate pair, and [the ByteAsk guide](docs/byteask-integration.md) for MCP registration and the headless wrapper. Default MCP tools run offline; generation is disabled unless explicitly enabled by the server owner.

## What is frozen

Qualification requires stable eligible failure evidence in at least 8/10 original runs. The paired gate requires the retained pre-patch bundle identity, matching original source/build recipe, at least 16 matching original failures in 20 runs, and zero candidate failures. Compiler errors, changed inputs and unrelated crashes cannot earn approval. Builds and checks run on disposable filesystem allowlists with filtered environments and isolated networking.

Receipts bind recorded bytes and finite executions. They are not authorship signatures or proofs for every input. The live comparison measures final acceptance of the same repair; it does not measure MCP-guided repair or a better repair model.

## Earlier verifier-generation research

Automatic verifier generation is a separate, incomplete experiment. The earlier 12-observation DeepSeek pilot had zero fail-to-pass successes and seven historical token-limit violations. Its outcomes remain available in [the original pilot report](docs/phase-logs/pilot-outcome-2026-10-03.md). The repaired v5 protocol has no new paid observations. No generation-quality win is claimed. [Repair details](docs/repairs/README.md) · [Original implementation plan](docs/superpowers/plans/2026-10-01-proofsmith.md).
