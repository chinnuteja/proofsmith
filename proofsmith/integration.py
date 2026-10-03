"""Generate a verifier before headless patching, then replay it on the patched tree."""
import json
import os
import subprocess
import uuid
from pathlib import Path

from proofsmith import config
from proofsmith.eval.runner import atomic_json
from proofsmith.mcp_server import create_server, local_instance, reference_client
from proofsmith.pipeline import make_verifier
from proofsmith.agent.loop import Budget
from proofsmith.freeze import verify_bundle


def gated_run(issue_path: Path, task: str, repo: Path) -> int:
    from proofsmith.ledger import Ledger, LEDGER_PATH
    from proofsmith.llm import LLMClient

    issue = json.loads(issue_path.read_text())
    instance = local_instance(repo, issue["title"], issue["body"])
    work = config.RESULTS / "integration" / ("gate-" + uuid.uuid4().hex[:12])
    fake = os.environ.get("PROOFSMITH_FAKE_LLM") == "reference"
    client = reference_client(repo) if fake else LLMClient(config.EVAL_MODEL, Ledger(LEDGER_PATH), instance.id)
    result = make_verifier(instance, client, Budget(config.MAX_STEPS, config.MAX_TOTAL_TOKENS, config.MAX_WALL_S), work / "bundle")
    if result.status != "accepted" or result.bundle_dir is None:
        atomic_json(work / "gate.json", {"status": "NO_VERIFIER", "reason": result.reason})
        print(f"GATED: NO VERIFIER ({result.reason})")
        return 2
    work.mkdir(parents=True, exist_ok=True)
    with (work / "byteask.jsonl").open("w") as stdout, (work / "byteask.stderr").open("w") as stderr:
        process = subprocess.run(["byteask", "exec", task], cwd=repo, stdout=stdout, stderr=stderr, check=False)
    if process.returncode:
        atomic_json(work / "gate.json", {"status": "PATCHER_ERROR", "exit_code": process.returncode})
        print(f"GATED: PATCHER ERROR ({process.returncode})")
        return 2
    checked = verify_bundle(result.bundle_dir, repo, instance.build, config.EVAL_N, config.WORK / "integration" / work.name)
    passed = checked.build_ok and checked.fails == 0
    atomic_json(work / "gate.json", {"status": "PASS" if passed else "FAIL", "build_ok": checked.build_ok,
        "fails": checked.fails, "n": checked.n, "reference_mode": fake,
        "evidence_kinds": [r.evidence.kind for r in checked.runs]})
    print(f"GATED: {'PASS' if passed else 'FAIL'} ({checked.fails}/{checked.n} failures; {work})")
    return 0 if passed else 1
