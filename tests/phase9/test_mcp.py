"""Exercise actual SDK client/server stdio and real C++ verification, without a key."""
import asyncio
import json
import os
import shutil
import sys

import pytest

from proofsmith import config
from proofsmith.datasets.schema import apply_patch

pytestmark = [pytest.mark.slow, pytest.mark.timeout(300)]


def test_mcp_reference_round_trip(tmp_path):
    from mcp import ClientSession, StdioServerParameters
    from mcp.client.stdio import stdio_client

    repo = tmp_path / "repo"
    shutil.copytree(config.REPO / "cases/orderd/buggy", repo)
    env = {k: v for k, v in os.environ.items() if k != "DEEPSEEK_API_KEY"}
    env.pop("PROOFSMITH_FAKE_LLM", None)
    env.pop("PROOFSMITH_ALLOW_GENERATION", None)
    env["PROOFSMITH_RESULTS_DIR"] = str(tmp_path / "mcp-results")

    def payload(result):
        assert not result.isError, result.content
        return result.structuredContent or json.loads(result.content[0].text)

    async def run():
        parameters = StdioServerParameters(command=sys.executable, args=["-m", "proofsmith.mcp_server"], env=env)
        async with stdio_client(parameters) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()
                names = {t.name for t in (await session.list_tools()).tools}
                assert names == {"seal_check", "verify", "check_patch", "evidence_check"}
                made = payload(await session.call_tool("seal_check", {"repo_path": str(repo),
                    "harness_path": str(config.REPO / "cases/orderd/reference_harness"), "oracle": "tsan"}))
                assert made["status"] == "VERIFIED", made
                assert made["harness_source"] == "user supplied; no model generation"
                buggy = payload(await session.call_tool("verify", {"bundle_path": made["bundle_path"], "repo_path": str(repo)}))
                assert buggy["build_ok"] and buggy["fails"] == config.EVAL_N
                apply_patch(repo, config.REPO / "cases/orderd/variants/scoped_cancel.patch")
                fixed = payload(await session.call_tool("verify", {"bundle_path": made["bundle_path"], "repo_path": str(repo)}))
                assert fixed["passes"] and fixed["fails"] == 0
                baseline = tmp_path / "original"
                shutil.copytree(config.REPO / "cases/orderd/buggy", baseline)
                gated = payload(await session.call_tool("check_patch", {"bundle_path": made["bundle_path"],
                    "baseline_path": str(baseline), "candidate_path": str(repo),
                    "expected_bundle_id": made["bundle_id"]}))
                assert gated["status"] == "VERIFIED", gated
                gate_receipt = json.loads(__import__('pathlib').Path(gated["receipt_path"]).read_text())
                assert gate_receipt["harness_source"] == "user supplied; no model generation"
                integrity = payload(await session.call_tool("evidence_check", {"evidence_path": str(__import__('pathlib').Path(gated['receipt_path']).parent)}))
                assert integrity["matches"]
                assert not (repo / "proofsmith_harness").exists()
                return {"schema": "proofsmith.integration/1", "mode": "reference fixture over real MCP stdio",
                        "make": made, "buggy": buggy, "fixed": fixed, "patch_gate": gated}

    transcript = asyncio.run(run())
    (tmp_path / "transcript.json").write_text(json.dumps(transcript, indent=2))
    if os.environ.get("PROOFSMITH_RECORD_INTEGRATION") == "1":
        (config.RESULTS / "integration").mkdir(parents=True, exist_ok=True)
        (config.RESULTS / "integration/reference_transcript.json").write_text(json.dumps(transcript, indent=2))
