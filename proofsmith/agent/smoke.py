"""Live plumbing smoke. Uses deepseek-flash and the shared agent loop."""

from __future__ import annotations

from pathlib import Path

from proofsmith.agent.loop import AgentResult, Budget, run_agent
from proofsmith.agent.tools import ToolSet
from proofsmith.config import DEV_MODEL, MAX_STEPS, MAX_TOTAL_TOKENS, MAX_WALL_S, REPO, RUNS, WORK
from proofsmith.datasets.schema import Instance
from proofsmith.ledger import LEDGER_PATH, BudgetExceeded, Ledger
from proofsmith.llm import LLMClient
from proofsmith.sandbox import Sandbox

PHASE_CEILING_USD = 0.10
SMOKE_RUN_ID = "live-smoke"

# The task sentence is the phase plan's live-smoke prompt.
SMOKE_USER = (
    "Use list_dir and read_file to find the names of the two mutex members of OrderBook, "
    "then call finish(variant='plain', summary=<the two names>)."
)
SMOKE_SYSTEM = (
    "You are a tool-using agent inspecting one source tree. "
    "Use only the provided tools. The tree has no network access. "
    "Be brief. On every turn call a tool. "
    "Call finish when you have the answer the user asked for, or abstain if you cannot. "
    "The finish summary must contain the answer itself."
)


def run_smoke() -> AgentResult:
    ledger = Ledger(LEDGER_PATH)
    if ledger.spent_usd() >= PHASE_CEILING_USD:
        raise BudgetExceeded(f"phase ceiling ${PHASE_CEILING_USD:.2f} already reached")
    instance = Instance.model_validate_json(
        (REPO / "cases" / "orderd" / "instance.json").read_text(encoding="utf-8")
    )
    source = instance.source.path or ""
    src = Path(source)
    if not src.is_absolute():
        src = REPO / src
    sandbox = Sandbox.create(src, SMOKE_RUN_ID)
    work = WORK / "sandboxes" / SMOKE_RUN_ID / "work"
    tools = ToolSet(sandbox, instance.build, work)
    tools.instance_id = instance.id
    client = LLMClient(DEV_MODEL, ledger, SMOKE_RUN_ID)
    client.system_name = "smoke"
    budget = Budget(MAX_STEPS, MAX_TOTAL_TOKENS, MAX_WALL_S)
    return run_agent(client, SMOKE_SYSTEM, SMOKE_USER, tools, budget, RUNS / SMOKE_RUN_ID)
