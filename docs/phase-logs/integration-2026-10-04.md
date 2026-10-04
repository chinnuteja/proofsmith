# Moderate integration release

Scope authorized: finish the practical verification tool and ByteAsk/CI integration through moderate difficulty. Reliable automatic verifier generation and new paid evaluation runs are excluded.

## Delivered behavior

- Offline MCP defaults: seal_check, verify, check_patch, evidence_check. Generation requires PROOFSMITH_ALLOW_GENERATION=1 or explicitly labelled fixture mode.
- ByteAsk headless runner: validate a supplied frozen check, keep the original source untouched, patch a separate candidate using workspace-write, then independently gate both snapshots. Preserve JSONL, stderr, identities and portable JSON/HTML evidence. Bound turns and wall time; terminate the CLI process group on timeout.
- Actual ByteAsk registration and tool-approval settings, isolated project-local installation, setup guide and CI workflow.
- Installable 0.2.0 wheel includes the runtime header, prompts, report templates and static assets. Source-checkout demos and research remain separate from the installed gate.

## Validation

The published v0.1.15 asset's checksum matched SHA256SUMS. The binary reports byteask 0.1.0. Its proprietary binary is excluded from the package. Installation receipt: results/byteask-installation.json.

Actual ByteAsk CLI + official Proofsmith MCP: scripted localhost Responses fixture, four provider responses, seal_check/check_patch/evidence_check succeeded. Actual headless CLI: scripted fixture requested a real sandboxed shell edit; the independent gate recorded original target failures 20/20 and candidate failures 0/20. No cloud model request or account sign-in. Evidence and raw JSONL: results/integration/byteask-complete/. These are plumbing tests, not model intelligence or benchmark evidence.

The actual binary required namespaced tool schemas and explicit per-tool approval for unattended MCP use. Early transport attempts failed while adapting these details; the final success is recorded. No shell-sandbox bypass was used.

Targeted integration suite: 20 passed, 1 deselected, 145.96 seconds. Includes the real SDK stdio C++ check, policy regressions, headless fix/rejection/error, identity protection and timeout handling. The controlled full TSan demo was already exercised in the preceding release.

Configuration/site/reporting: 7 passed, 50.51 seconds. The first documentation pass found a missing company-claim reference; the final template records C4/C5 and links the actual local test receipt.

Local CI: supplied assertion qualified, fixed candidate VERIFIED, unchanged candidate REJECTED, all manifests checked. Receipt: results/integration/ci-smoke/summary.json. The arithmetic fixture is deliberately simple. GitHub-hosted execution remains untested.

Installed wheel: real qualification, original 20/20 failures and fixed 0/20, HTML/runtime resources present, all four offline MCP tools discoverable. Receipt: results/integration-wheel-check.json. This reused the existing Python dependencies and WSL C++ toolchain.

Browser: 1280 and 390 widths, no horizontal overflow or JavaScript errors, rendered measurements match repository JSON. Receipt: results/integration-browser-check.json. Screenshots: docs/evidence/integration/.

Protocol v4 is archived. Active v5 hashes the revised source; it has no paid observations. Existing negative pilot results and the DeepSeek ledger are preserved. Additional model spend: zero.

Clean-clone verification passed at source commit 2501fbc869c6c0a6f3f01275d683b802aaba63b1. The clone started clean without .env or model credentials, validated protocol v5, checked twelve evidence packages, confirmed the tested wheel identity, and freshly repeated both the CI acceptance/rejection and actual ByteAsk MCP/headless workflows using the scripted localhost provider. It reused the installed WSL toolchain, Python dependencies and ByteAsk binary; no upstream source mirrors were needed. Receipt: results/integration-reproduction.json.

No publication, push, outreach or account login is performed by this release.
