# Use Proofsmith with ByteAsk

Proofsmith is a local C/C++ verification companion. Supply a check, qualify it on the original source, freeze its identity, and gate a separate proposed fix. Automatic verifier generation is outside this integration's default scope.

## What is tested

The actual published ByteAsk v0.1.15 Linux binary (which reports `byteask 0.1.0`) discovered and called `seal_check`, `check_patch`, and `evidence_check` over MCP. A scripted localhost Responses provider selected the tools; the compiler, tool server and checks ran for real. The supplied arithmetic fixture failed on the original source and passed on the fixed source. This validates transport and configuration, not model intelligence, a signed-in cloud session, or superiority over ByteAsk.

The same actual ByteAsk binary also passed the headless runner: the scripted provider requested a real sandboxed shell edit, and Proofsmith independently gated the resulting candidate. The wrapper has separate checks for accepted fixes, unchanged candidates, patcher errors, incorrect bundle identities and timeouts. CI qualification, paired gates and manifest checks also run locally with the real compiler. GitHub execution itself remains untested until the workflow runs in your repository.

## Install in Linux or WSL

The release ZIP includes the wheel, source, setup scripts and portable test evidence. From its extracted directory, install MCP support with:

```bash
python -m pip install 'artifacts/proofsmith-0.2.0-py3-none-any.whl[mcp]'
```

From the Proofsmith checkout, use Python 3.12 or newer:

```bash
sudo apt-get install clang llvm cmake ninja-build bubblewrap iproute2
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -e '.[dev,mcp]'
bash scripts/ci_gate.sh /tmp/proofsmith-first-check
```

The output directory must be new. Open `fixed/index.html` and `unfixed/index.html` inside it. The fixture is intentionally simple and serves as an installation test. For the stronger supplied TSan demonstration, run `proofsmith demo gate`.

ByteAsk can use your existing installation. For an isolated project-local installation on Linux x86_64:

```bash
bash scripts/install_byteask_local.sh
bash scripts/configure_byteask_local.sh
bash scripts/byteask_local.sh login --email you@company.com
```

The install script verifies the pinned engine download against the release's SHA256SUMS, installs under `.tools/`, and leaves global shell and debugger configuration alone. The launcher comes from ByteAsk's official distribution. `.tools/` is ignored by Git. Sign-in belongs to you; no credentials are included in the project. The registration uses the active Python environment, so keep that environment installed.

## Register MCP in an existing ByteAsk installation

ByteAsk uses TOML, rather than the generic `mcpServers` JSON shape. The actual installed CLI requires `--` before the server command:

```bash
byteask mcp add proofsmith --env PROOFSMITH_ALLOW_GENERATION=0 \
  --env DEEPSEEK_API_KEY= -- /absolute/path/to/venv/bin/proofsmith mcp
byteask mcp list
```

In your ByteAsk `config.toml`, use:

```toml
[mcp_servers.proofsmith]
command = "/absolute/path/to/venv/bin/proofsmith"
args = ["mcp"]
env = { PROOFSMITH_ALLOW_GENERATION = "0", DEEPSEEK_API_KEY = "", PROOFSMITH_RESULTS_DIR = "/work/proofsmith-results" }
enabled = true
startup_timeout_sec = 30
tool_timeout_sec = 600
```

ByteAsk's default tool timeout is too short for repeated C++ runs. The server exposes four tools by default:

| Tool | Purpose |
|---|---|
| `seal_check(repo_path, harness_path, oracle)` | Qualify a supplied check in 10 runs and return its bundle path and identity. |
| `check_patch(bundle_path, baseline_path, candidate_path, expected_bundle_id)` | Reproduce the original target and test the candidate in 20 runs per tree. |
| `verify(bundle_path, repo_path)` | Replay on one disposable source copy. Use the paired gate to approve a fix. |
| `evidence_check(evidence_path, expected_manifest_sha256)` | Check the portable files, optionally against a separately retained manifest digest. |

For non-CMake projects, place a BuildRecipe JSON in `.proofsmith-build.json` **before qualification**. All MCP paths are absolute paths as seen by the server. A Windows client can launch a WSL server, but supply Linux paths to its tools. Source symlinks are currently unsupported.

In an interactive ByteAsk session, approve the local tools when prompted. For unattended use with checks you trust, the installed binary also supports approval for individual tools:

```toml
[mcp_servers.proofsmith.tools.seal_check]
approval_mode = "approve"
[mcp_servers.proofsmith.tools.check_patch]
approval_mode = "approve"
[mcp_servers.proofsmith.tools.evidence_check]
approval_mode = "approve"
```

These approve these named tools, which compile and execute supplied checks. They do not change the shell sandbox. Without them, the tested binary's `approval_policy = "never"` rejects MCP calls needing approval. The localhost transport test exercises this exact configuration.

Suggested session instructions:

> Qualify my supplied check against /work/original using seal_check. Retain its bundle identity. Patch only /work/candidate. Call check_patch with the original tree, candidate and retained identity. Show the verdict and evidence report. Treat INCONCLUSIVE as unresolved.

Keep `/work/original` pristine. The gate covers the supplied check and those source snapshots; it does not prove general patch correctness.

## Headless patching

First run `proofsmith seal` as described in [the verification guide](verification-tool.md), and retain its bundle ID. Put the repair task in a UTF-8 file. Then:

```bash
proofsmith byteask-patch --repo /work/original --bundle /work/sealed/bundle \
  --expect-bundle-id <retained-sha256> --instance /work/instance.json \
  --task-file /work/repair.txt --out /work/byteask-run \
  --max-turns 30 --timeout 1800
```

`byteask` must be on PATH and signed in, or configured with your own model provider. For the local installation:

```bash
export PATH="$PWD/.tools/byteask:$PATH"
export BYTEASK_HOME="$PWD/.tools/byteask-home"
export BYTEASK_NO_UPDATE_CHECK=1
```

The runner validates and snapshots the original source and frozen check before invoking ByteAsk. ByteAsk gets the separate `candidate/` directory with `workspace-write`, JSONL output, ephemeral sessions, a turn limit and a wall-time limit. The gate independently checks original and candidate copies afterward. Timeouts terminate the CLI process group. No patch is automatically applied to your original checkout.

The output contains `gate.json`, `byteask.jsonl`, `byteask.stderr`, `baseline/`, `candidate/`, `frozen/`, and, when the patcher completes, `evidence/index.html` and `evidence/receipt.json`. Exit codes are 0 VERIFIED, 1 REJECTED and 2 unresolved/error. Build failures and patcher failures cannot produce a passing gate. Use the candidate only after reviewing its diff and receipt.

This command invokes your ByteAsk model and consumes its account/provider usage. The verification server and gate make no model requests. ByteAsk usage is separate from Proofsmith's DeepSeek ledger.

## CI and local transport regression

[The workflow](../.github/workflows/verification-tool.yml) runs the offline supplied fixture and uploads its evidence on success or failure. It needs no model key. For your own CI, retain the original snapshot, supplied bundle and pre-patch ID as trusted inputs, run `proofsmith gate`, propagate its exit code, and upload the complete evidence directory even when the gate fails.

To repeat the actual ByteAsk integration without a cloud account:

```bash
bash scripts/check_byteask_transport.sh /tmp/proofsmith-byteask-transport
```

This is an explicitly scripted localhost test. It does not demonstrate a model-generated fix. Use a new output path on every run; successful receipts remain auditable.

Sources: [ByteAsk MCP and configuration](https://docs.byteask.ai/docs/features), [headless mode](https://docs.byteask.ai/docs/headless), [published CLI releases](https://github.com/ByteAsk/cli/releases). The exact registration and approval syntax above was also checked against the installed binary.
