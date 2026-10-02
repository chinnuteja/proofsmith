"""B0, B1, and Proofsmith. Same tools, same budget, same model."""

from __future__ import annotations

import shutil
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path

from proofsmith.agent.loop import Budget, run_agent
from proofsmith.agent.tools import ToolSet
from proofsmith.config import REPO, RUNS, WORK
from proofsmith.datasets.schema import Instance, materialize
from proofsmith.freeze import freeze
from proofsmith.llm import Usage
from proofsmith.oracles.variants import VARIANTS
from proofsmith.pipeline import make_verifier
from proofsmith.sandbox import Sandbox

_PROMPTS = Path(__file__).resolve().parent / "prompts"
_BASELINES = {"b0", "b1"}


def _read(name: str) -> str:
    return (_PROMPTS / name).read_text(encoding="utf-8")


def _system_prompt(system: str) -> str:
    return _read(f"{system}.md").strip() + "\n\n" + _read("harness_contract.md").strip() + "\n"


def _user_prompt(instance: Instance) -> str:
    return f"Issue title: {instance.issue.title}\n\nIssue body:\n{instance.issue.body}\n"


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _usage_dict(usage: Usage) -> dict:
    return {
        "prompt_tokens": usage.prompt_tokens,
        "completion_tokens": usage.completion_tokens,
        "reasoning_tokens": usage.reasoning_tokens,
        "cache_hit_tokens": usage.cache_hit_tokens,
    }


def _rel(path: Path) -> str:
    try:
        return path.resolve().relative_to(REPO.resolve()).as_posix()
    except ValueError:
        return path.as_posix()


def _run_dir(llm, work: Path, name: str) -> Path:
    folder = f"{name}-{uuid.uuid4().hex[:8]}"
    if getattr(llm, "model", "") == "deepseek-v4-pro":
        path = RUNS / folder
    else:
        path = work / "runs" / folder
    path.mkdir(parents=True, exist_ok=True)
    return path


def _ensure_harness(repo: Path) -> None:
    harness = repo / "proofsmith_harness"
    if not harness.is_dir():
        if harness.exists():
            harness.unlink()
        harness.mkdir(parents=True)


def _freeze_baseline(
    system: str,
    repo: Path,
    instance: Instance,
    llm,
    usage: Usage,
    cost: float,
    wall: float,
    trajectory: str,
    status: str,
    variant: str | None,
    reason: str | None,
    out_dir: Path,
) -> Path:
    _ensure_harness(repo)
    spec = VARIANTS.get(variant or "")
    meta = {
        "schema": "proofsmith.verifier/1",
        "system": system,
        "instance_id": instance.id,
        "status": status,
        "abstain_reason": reason,
        "oracle": None,
        "variant": variant,
        "signature": None,
        "runtime": {"n": 0, "k": 0, "fails": 0, "signatures": {}},
        "flags": {
            "cxxflags": spec.cxxflags if spec else "",
            "ldflags": spec.ldflags if spec else "",
            "env": dict(spec.env) if spec else {},
        },
        "model": getattr(llm, "model", "") or "",
        "usage": _usage_dict(usage),
        "cost_usd": cost,
        "wall_s": wall,
        "trajectory": trajectory,
        "created_at": _now(),
    }
    return freeze(repo, meta, out_dir)


def _baseline(system: str, instance: Instance, llm, budget: Budget, out_dir: Path) -> Path:
    started = time.monotonic()
    cost_before = float(sum(getattr(llm, "costs", []) or []))
    token = uuid.uuid4().hex[:8]
    work = WORK / "systems" / f"{instance.id}-{system}-{token}"
    if work.exists():
        shutil.rmtree(work)
    work.mkdir(parents=True)
    sandbox = None
    try:
        tree = materialize(instance, work / "src")
        sandbox = Sandbox.create(tree, f"{instance.id}-{system}-{token}")
        tools = ToolSet(sandbox, instance.build, work / "tools")
        tools.instance_id = instance.id
        run_dir = _run_dir(llm, work, f"{instance.id}-{system}")
        result = run_agent(
            llm,
            _system_prompt(system),
            _user_prompt(instance),
            tools,
            budget,
            run_dir,
        )
        cost = float(sum(getattr(llm, "costs", []) or [])) - cost_before
        wall = time.monotonic() - started
        trajectory = _rel(run_dir / "trajectory.jsonl")
        variant = result.final.get("variant") if isinstance(result.final.get("variant"), str) else None
        illegal = sandbox.illegal_changes()
        if result.status == "finished" and variant in VARIANTS and not illegal:
            status = "submitted"
            reason = None
        else:
            status = "gave_up"
            variant = None
            if illegal:
                reason = "harness modified files outside proofsmith_harness/"
            elif result.status == "abstained":
                reason = str(result.final.get("reason") or "model abstained")
            elif result.status == "budget_exhausted":
                reason = "budget exhausted"
            else:
                reason = str(result.final.get("error") or result.status or "gave up")
        return _freeze_baseline(
            system,
            sandbox.repo,
            instance,
            llm,
            result.usage,
            cost,
            wall,
            trajectory,
            status,
            variant,
            reason,
            out_dir,
        )
    finally:
        if sandbox is not None:
            sandbox.destroy()
        if work.exists():
            shutil.rmtree(work, ignore_errors=True)


def run_system(system: str, instance: Instance, llm, budget: Budget, out_dir: Path) -> Path:
    if system == "proofsmith":
        result = make_verifier(instance, llm, budget, out_dir)
        if result.bundle_dir is not None:
            return result.bundle_dir
        raise RuntimeError(result.reason or "proofsmith produced no bundle")
    if system not in _BASELINES:
        raise ValueError(f"unknown system {system}")
    return _baseline(system, instance, llm, budget, out_dir)
