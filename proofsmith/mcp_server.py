"""Stdio integration using the official MCP SDK's supported v1 interface."""
from __future__ import annotations

import os
import uuid
import tempfile
from collections import Counter
from pathlib import Path

from proofsmith import config
from proofsmith.agent.loop import Budget
from proofsmith.datasets.schema import BuildRecipe, Instance, Issue, Source
from proofsmith.freeze import verify_bundle
from proofsmith.pipeline import make_verifier as generate


def local_instance(repo: Path, title: str, body: str) -> Instance:
    repo = repo.resolve()
    if not repo.is_dir():
        raise ValueError("repo_path must be an existing directory")
    recipe_file = repo / ".proofsmith-build.json"
    if recipe_file.exists():
        recipe = BuildRecipe.model_validate_json(recipe_file.read_text())
    elif (repo / "CMakeLists.txt").is_file():
        recipe = BuildRecipe(system="cmake", test_command="ctest --output-on-failure")
    else:
        raise ValueError("provide a .proofsmith-build.json BuildRecipe for a repository without CMake")
    return Instance(schema="proofsmith.instance/1", id="local-" + uuid.uuid4().hex[:12], track="demo",
                    source=Source(kind="dir", path=str(repo)), issue=Issue(title=title, body=body), build=recipe)


def reference_client(repo: Path):
    """Explicit fixture mode; never represents a model-generated benchmark win."""
    from proofsmith.llm import FakeLLM, LLMResponse, ToolCall, Usage
    from proofsmith.oracles.builds import snapshot_sha256

    fixture = config.REPO / "cases/orderd"
    if snapshot_sha256(repo) != snapshot_sha256(fixture / "buggy"):
        raise ValueError("reference mode supports only the unchanged orderd fixture")
    def reply(content, calls):
        return LLMResponse(content, None, calls, Usage(0, 0, 0, 0), "tool_calls" if calls else "stop")
    import json
    calls = [ToolCall(name, "write_file", {"path": "proofsmith_harness/" + name,
              "content": (fixture / "reference_harness" / name).read_text()}) for name in ("build.sh", "harness.cpp")]
    calls.append(ToolCall("finish", "finish", {"variant": "tsan", "summary": "Explicit hand-written reference fixture"}))
    return FakeLLM([reply(json.dumps({"oracles": ["tsan"], "rationale": "reference fixture", "suspects": []}), []),
                    reply(None, calls)])


def create_server():
    from mcp.server.fastmcp import FastMCP

    server = FastMCP("Proofsmith")

    @server.tool()
    def make_verifier(repo_path: str, issue_title: str, issue_body: str) -> dict:
        """Generate and freeze a failing check before patching. Live mode incurs metered model cost."""
        from proofsmith.llm import LLMClient
        from proofsmith.ledger import Ledger, LEDGER_PATH

        repo = Path(repo_path).resolve()
        instance = local_instance(repo, issue_title, issue_body)
        fake = os.environ.get("PROOFSMITH_FAKE_LLM") == "reference"
        client = reference_client(repo) if fake else LLMClient(config.EVAL_MODEL, Ledger(LEDGER_PATH), instance.id)
        client.system_name = "proofsmith"
        bundle = config.RESULTS / "integration" / instance.id / "bundle"
        result = generate(instance, client, Budget(config.MAX_STEPS, config.MAX_TOTAL_TOKENS, config.MAX_WALL_S), bundle)
        if fake and result.bundle_dir:
            import json
            metadata_path = result.bundle_dir / "verifier.json"
            metadata = json.loads(metadata_path.read_text())
            metadata["harness_source"] = "hand-written reference fixture; no model calls"
            metadata_path.write_text(json.dumps(metadata, indent=2, sort_keys=True) + "\n")
        from proofsmith.gate import bundle_id
        return {"status": result.status, "oracle": result.oracle, "signature": result.signature,
                "bundle_path": str(result.bundle_dir) if result.bundle_dir else None,
                "reason": result.reason, "cost_usd": result.cost_usd,
                "harness_source": "hand-written reference fixture" if fake else "model generated",
                "bundle_id": bundle_id(result.bundle_dir) if result.bundle_dir else None}

    @server.tool()
    def verify(bundle_path: str, repo_path: str) -> dict:
        """Replay a frozen check on a repository after patching. No model or key is required."""
        instance = local_instance(Path(repo_path), "Replay", "")
        from proofsmith.gate import _copy_source
        config.WORK.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(prefix="mcp-verify-", dir=config.WORK) as directory:
            work = Path(directory)
            _copy_source(Path(repo_path), work / "source")
            result = verify_bundle(Path(bundle_path), work / "source", instance.build, config.EVAL_N,
                                   work / "run")
        return {"build_ok": result.build_ok, "fails": result.fails, "n": result.n,
                "evidence_kinds": dict(Counter(r.evidence.kind for r in result.runs)),
                "passes": result.build_ok and result.fails == 0}

    @server.tool()
    def check_patch(bundle_path: str, baseline_path: str, candidate_path: str, expected_bundle_id: str) -> dict:
        """Gate a patch using a pinned pre-patch verifier. Source trees stay untouched; no model cost.

        VERIFIED means this check passed after reproducing the original failure, not general patch correctness.
        REJECTED means the same target still fires. INCONCLUSIVE covers build or evidence failures.
        """
        from proofsmith.gate import check_patch as gate
        instance = local_instance(Path(baseline_path), "Patch verification", "")
        out = config.RESULTS / "integration" / instance.id / "gate"
        receipt = gate(Path(bundle_path), Path(baseline_path), Path(candidate_path), instance.build,
                       out, expected_bundle_id)
        def measurements(side):
            return {k: v for k, v in receipt.get(side, {}).items() if k != "runs"}
        return {"status": receipt["status"], "reason": receipt["reason"], "exit_code": receipt["exit_code"],
                "bundle_id": receipt.get("bundle_id"), "baseline": measurements("baseline"),
                "candidate": measurements("candidate"), "receipt_path": str(out / "receipt.json"),
                "report_path": str(out / "index.html"), "limitation": receipt["limitation"]}

    return server


def main():
    create_server().run(transport="stdio")


if __name__ == "__main__":
    main()
