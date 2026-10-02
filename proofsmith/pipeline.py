"""Issue to oracle to harness to accept, abstain, or skip."""

from __future__ import annotations

import json
import shutil
import time
import uuid
from collections import Counter
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

from pydantic import BaseModel, ValidationError

from proofsmith.agent.loop import Budget, run_agent
from proofsmith.agent.tools import ToolSet
from proofsmith.config import REPO, RUNS, RUNTIME_K, RUNTIME_N, RUN_TIMEOUT_S, WORK
from proofsmith.datasets.schema import Instance, materialize
from proofsmith.freeze import freeze
from proofsmith.harness import compile_harness
from proofsmith.llm import Usage
from proofsmith.oracles.acceptance import decide
from proofsmith.oracles.builds import build_variant
from proofsmith.oracles.runner import run_n
from proofsmith.oracles.variants import VARIANTS
from proofsmith.sandbox import Sandbox

_ALLOWED = ("tsan", "asan_ubsan", "assertion")
_FALLBACK = ("asan_ubsan", "tsan", "assertion")
_ORACLE_VARIANT = {"tsan": "tsan", "asan_ubsan": "asan_ubsan", "assertion": "plain"}
_MAX_ORACLES = 2
_MAX_ATTEMPTS = 3
_SKIP_REASON = "existing test already fails; Proofsmith not needed"
_ILLEGAL = "harness modified files outside proofsmith_harness/"
_PROMPTS = Path(__file__).resolve().parent / "prompts"


class Classification(BaseModel):
    oracles: list[str]
    rationale: str
    suspects: list[str]


@dataclass
class VerifierResult:
    status: str
    bundle_dir: Path | None
    oracle: str | None
    signature: str | None
    reason: str
    attempts: list[dict]
    usage: Usage
    cost_usd: float
    wall_s: float
    extra: dict = field(default_factory=dict)


def _read(name: str) -> str:
    return (_PROMPTS / name).read_text(encoding="utf-8")


def _add(total: Usage, extra: Usage) -> Usage:
    return Usage(
        total.prompt_tokens + extra.prompt_tokens,
        total.completion_tokens + extra.completion_tokens,
        total.reasoning_tokens + extra.reasoning_tokens,
        total.cache_hit_tokens + extra.cache_hit_tokens,
    )


def _tokens(usage: Usage) -> int:
    return usage.prompt_tokens + usage.completion_tokens


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _normalize_oracles(names: list[str]) -> list[str]:
    kept: list[str] = []
    for name in names:
        if name not in _ALLOWED or name in kept:
            continue
        kept.append(name)
        if len(kept) == _MAX_ORACLES:
            break
    return kept


def _parse_classification(content: str | None) -> Classification | None:
    if not content:
        return None
    text = content.strip()
    if text.startswith("```"):
        lines = text.splitlines()
        if lines and lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip().startswith("```"):
            lines = lines[:-1]
        text = "\n".join(lines).strip()
    try:
        payload = json.loads(text)
    except json.JSONDecodeError:
        return None
    try:
        parsed = Classification.model_validate(payload)
    except ValidationError:
        return None
    return parsed


def classify(issue: dict, repo_summary: str, llm) -> Classification:
    system = _read("classify.md")
    title = str(issue.get("title") or "")
    body = str(issue.get("body") or "")
    user = f"Issue title: {title}\n\nIssue body:\n{body}\n\nRepository summary:\n{repo_summary}\n"
    messages = [
        {"role": "system", "content": system},
        {"role": "user", "content": user},
    ]
    for _ in range(2):
        response = llm.chat(messages, None, 1024)
        parsed = _parse_classification(response.content)
        if parsed is None:
            messages.append({"role": "assistant", "content": response.content or ""})
            messages.append(
                {
                    "role": "user",
                    "content": "That was not the JSON object requested. Return only the JSON object.",
                }
            )
            continue
        return Classification(
            oracles=_normalize_oracles(parsed.oracles),
            rationale=parsed.rationale,
            suspects=parsed.suspects,
        )
    return Classification(
        oracles=_normalize_oracles(list(_FALLBACK)),
        rationale="classifier output was not valid JSON",
        suspects=[],
    )


def _shell_quote(text: str) -> str:
    return "'" + text.replace("'", "'\"'\"'") + "'"


def _target_names(compile_commands: Path | None) -> list[str]:
    if compile_commands is None or not compile_commands.is_file():
        return []
    try:
        entries = json.loads(compile_commands.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return []
    names: list[str] = []
    if not isinstance(entries, list):
        return []
    for entry in entries:
        if not isinstance(entry, dict):
            continue
        output = entry.get("output")
        if isinstance(output, str) and output:
            names.append(Path(output).name)
    return sorted(set(names))


def _repo_summary(repo: Path, compile_commands: Path | None) -> str:
    names = []
    for child in sorted(repo.iterdir(), key=lambda path: path.name):
        if child.name == ".git":
            continue
        names.append(child.name + ("/" if child.is_dir() else ""))
    readme = ""
    for candidate in ("README.md", "README", "readme.md"):
        path = repo / candidate
        if path.is_file():
            lines = path.read_text(encoding="utf-8", errors="replace").splitlines()[:120]
            readme = "\n".join(lines)
            break
    targets = "\n".join(_target_names(compile_commands))
    return (
        "Top level:\n"
        + "\n".join(names)
        + "\n\nREADME:\n"
        + readme
        + "\n\nBuild outputs:\n"
        + targets
        + "\n"
    )


def _tests_fail(sandbox: Sandbox, recipe, work: Path) -> tuple[bool, str]:
    build = build_variant(sandbox.repo, "plain", recipe, work / "existing")
    if not build.ok:
        return True, _SKIP_REASON
    if not recipe.test_command:
        return False, ""
    command = f"cd {_shell_quote(str(build.build_dir))} && {recipe.test_command}"
    result = sandbox.exec(command, RUN_TIMEOUT_S)
    if result.timed_out or result.exit_code != 0:
        return True, _SKIP_REASON
    return False, ""


def _histogram(runs) -> str:
    counts = Counter(run.evidence.kind for run in runs)
    if not counts:
        return "(none)"
    return ", ".join(f"{kind}={counts[kind]}" for kind in sorted(counts))


def _excerpt_text(text: str) -> str:
    return "\n".join(text.splitlines()[:80])[:4000]


def _excerpt(runs) -> str:
    for run in runs:
        if run.timed_out or run.exit_code != 0:
            path = Path(run.output_path)
            if path.is_file():
                return _excerpt_text(path.read_text(encoding="utf-8", errors="replace"))
    return ""


def _retry(reason: str, histogram: str, excerpt: str) -> str:
    return (
        _read("retry_feedback.md")
        .replace("{reason}", reason)
        .replace("{histogram}", histogram)
        .replace("{first_failure_excerpt}", excerpt)
    )


def _clear_harness(repo: Path) -> None:
    harness = repo / "proofsmith_harness"
    if harness.exists():
        shutil.rmtree(harness)
    harness.mkdir()


def _rel_repo(path: Path) -> str:
    try:
        return path.resolve().relative_to(REPO.resolve()).as_posix()
    except ValueError:
        return path.as_posix()


def _child_budget(budget: Budget, usage: Usage, steps: int, started: float) -> Budget | None:
    remain_steps = budget.max_steps - steps
    remain_tokens = budget.max_total_tokens - _tokens(usage)
    remain_wall = int(budget.max_wall_s - (time.monotonic() - started))
    if remain_steps <= 0 or remain_tokens <= 0 or remain_wall <= 0:
        return None
    return Budget(remain_steps, remain_tokens, remain_wall)


def _blank(status: str, reason: str, usage: Usage, cost: float, wall: float, attempts: list[dict]) -> VerifierResult:
    return VerifierResult(status, None, None, None, reason, attempts, usage, cost, wall)


def _system_prompt(oracle: str) -> str:
    return "\n\n".join(
        [
            _read("proofsmith_system.md").strip(),
            _read(f"oracle_{oracle}.md").strip(),
            _read("harness_contract.md").strip(),
        ]
    )


def _user_prompt(issue: dict, rationale: str) -> str:
    return (
        f"Issue title: {issue.get('title') or ''}\n\n"
        f"Issue body:\n{issue.get('body') or ''}\n\n"
        f"Why this oracle:\n{rationale}\n"
    )


def _judge(sandbox: Sandbox, recipe, oracle: str, work: Path) -> dict:
    illegal = sandbox.illegal_changes()
    if illegal:
        return _verdict(False, _ILLEGAL, "(none)", "", None, 0, {})
    variant = _ORACLE_VARIANT[oracle]
    built = build_variant(sandbox.repo, variant, recipe, work / "judge" / oracle)
    if not built.ok:
        log = ""
        if built.log_path.is_file():
            log = built.log_path.read_text(encoding="utf-8", errors="replace")
        return _verdict(False, "project build failed for the oracle variant", "(none)", _excerpt_text(log), None, 0, {})
    out_dir = work / "judge-harness" / oracle
    compiled = compile_harness(sandbox.repo, built, variant, out_dir)
    if not compiled.ok or compiled.binary is None:
        log = ""
        if compiled.log_path.is_file():
            log = compiled.log_path.read_text(encoding="utf-8", errors="replace")
        return _verdict(False, "harness failed to compile", "(none)", _excerpt_text(log), None, 0, {})
    runs = run_n(
        compiled.binary,
        variant,
        RUNTIME_N,
        RUN_TIMEOUT_S,
        sandbox.repo,
        str(sandbox.repo.resolve()),
        work / "judge-runs" / oracle,
    )
    decision = decide(runs, RUNTIME_K, oracle)
    fails = sum(1 for run in runs if run.timed_out or run.exit_code != 0)
    signatures: dict[str, int] = {}
    if decision.signature:
        signatures[decision.signature] = decision.count
    return _verdict(
        decision.accepted,
        decision.reason,
        _histogram(runs),
        _excerpt(runs),
        decision.signature,
        fails,
        signatures,
    )


def _verdict(accepted: bool, reason: str, histogram: str, excerpt: str, signature, fails: int, signatures: dict) -> dict:
    return {
        "accepted": accepted,
        "reason": reason,
        "histogram": histogram,
        "excerpt": excerpt,
        "signature": signature,
        "fails": fails,
        "signatures": signatures,
    }


def make_verifier(instance: Instance, llm, budget: Budget, out_dir: Path) -> VerifierResult:
    started = time.monotonic()
    usage = Usage(0, 0, 0, 0)
    steps = 0
    attempts: list[dict] = []
    reasons: list[str] = []
    cost_before = float(sum(getattr(llm, "costs", []) or []))
    _capture_chat(llm)
    run_token = uuid.uuid4().hex[:8]
    work = WORK / "pipeline" / f"{instance.id}-{run_token}"
    if work.exists():
        shutil.rmtree(work)
    work.mkdir(parents=True)
    sandbox = None
    accepted: dict | None = None

    def cost() -> float:
        return float(sum(getattr(llm, "costs", []) or [])) - cost_before

    def wall() -> float:
        return time.monotonic() - started

    try:
        tree = materialize(instance, work / "src")
        sandbox = Sandbox.create(tree, f"{instance.id}-{run_token}")
        failed, skip_reason = _tests_fail(sandbox, instance.build, work)
        if failed:
            return _blank("skipped", skip_reason, usage, cost(), wall(), attempts)

        summary = _repo_summary(sandbox.repo, _find_commands(work / "existing" / "plain"))
        issue = instance.issue.model_dump()
        before_calls = _chat_usage(llm)
        classification = classify(issue, summary, llm)
        usage = _add(usage, _usage_since(llm, before_calls))

        if not classification.oracles:
            reasons.append("classifier returned no oracle")
            bundle = _freeze_abstain(
                sandbox, instance, llm, usage, cost(), wall(), reasons, None, out_dir
            )
            return VerifierResult(
                "abstained", bundle, None, None, "NO VERIFIER: " + "; ".join(reasons), attempts, usage, cost(), wall()
            )

        last_trajectory = None
        for oracle in classification.oracles:
            child = _child_budget(budget, usage, steps, started)
            if child is None:
                reasons.append("budget exhausted")
                break
            outcome = _run_oracle(
                instance, llm, child, sandbox, oracle, classification.rationale, issue, work, attempts
            )
            usage = _add(usage, outcome["usage"])
            steps += outcome["steps"]
            if outcome.get("trajectory"):
                last_trajectory = outcome["trajectory"]
            if outcome["reason"]:
                reasons.append(outcome["reason"])
            if outcome["accepted"]:
                accepted = outcome
                break
            if outcome["stop"]:
                if "budget" not in " ".join(reasons):
                    reasons.append("budget exhausted")
                break

        if accepted:
            if sandbox.illegal_changes():
                reasons.append(_ILLEGAL)
            else:
                bundle = _freeze_accept(sandbox, instance, llm, usage, cost(), wall(), accepted, out_dir)
                return VerifierResult(
                    "accepted",
                    bundle,
                    accepted["oracle"],
                    accepted["signature"],
                    accepted["reason"],
                    attempts,
                    usage,
                    cost(),
                    wall(),
                )

        bundle = _freeze_abstain(
            sandbox, instance, llm, usage, cost(), wall(), reasons, last_trajectory, out_dir
        )
        return VerifierResult(
            "abstained",
            bundle,
            None,
            None,
            "NO VERIFIER: " + "; ".join(reasons),
            attempts,
            usage,
            cost(),
            wall(),
        )
    finally:
        if sandbox is not None:
            sandbox.destroy()
        if work.exists():
            shutil.rmtree(work, ignore_errors=True)


def _find_commands(build_dir: Path) -> Path | None:
    path = build_dir / "compile_commands.json"
    if path.is_file():
        return path
    return None


def _chat_usage(llm) -> int:
    return len(getattr(llm, "_proofsmith_usages", []) or [])


def _usage_since(llm, start_index: int) -> Usage:
    recorded = getattr(llm, "_proofsmith_usages", None)
    if recorded is None:
        return Usage(0, 0, 0, 0)
    total = Usage(0, 0, 0, 0)
    for item in recorded[start_index:]:
        total = _add(total, item)
    return total


def _capture_chat(llm):
    """Remember each response usage so the pipeline can share one budget.

    LLMClient and FakeLLM both return LLMResponse. Wrapping chat keeps the
    original object working for run_agent.
    """
    if getattr(llm, "_proofsmith_wrapped", False):
        return
    original = llm.chat
    recorded: list[Usage] = []

    def chat(messages, tools, max_tokens):
        response = original(messages, tools, max_tokens)
        recorded.append(response.usage)
        return response

    llm.chat = chat
    llm._proofsmith_usages = recorded
    llm._proofsmith_wrapped = True


def _run_oracle(instance, llm, budget, sandbox, oracle, rationale, issue, work, attempts) -> dict:
    _capture_chat(llm)
    state = {
        "accepted": False,
        "stop": False,
        "reason": "",
        "parts": [],
        "signature": None,
        "oracle": oracle,
        "attempts_used": 0,
        "trajectory": "",
        "usage": Usage(0, 0, 0, 0),
        "steps": 0,
        "fail_count": 0,
        "signatures": {},
    }
    run_dir = _run_dir(llm, work, f"{instance.id}-{oracle}")
    tools = ToolSet(sandbox, instance.build, work / "tools" / oracle)
    tools.instance_id = instance.id

    def on_finish(_finished: dict):
        state["attempts_used"] += 1
        verdict = _judge(sandbox, instance.build, oracle, work)
        attempts.append(
            {
                "oracle": oracle,
                "attempt": state["attempts_used"],
                "accepted": bool(verdict["accepted"]),
                "reason": verdict["reason"],
            }
        )
        if verdict["accepted"] and not sandbox.illegal_changes():
            state["accepted"] = True
            state["signature"] = verdict["signature"]
            state["reason"] = verdict["reason"]
            state["fail_count"] = verdict["fails"]
            state["signatures"] = verdict["signatures"]
            return None
        state["parts"].append(verdict["reason"])
        if state["attempts_used"] < _MAX_ATTEMPTS:
            return _retry(verdict["reason"], verdict["histogram"], verdict["excerpt"])
        state["reason"] = "; ".join(state["parts"])
        return None

    before = len(llm._proofsmith_usages)
    result = run_agent(
        llm,
        _system_prompt(oracle),
        _user_prompt(issue, rationale),
        tools,
        budget,
        run_dir,
        on_finish=on_finish,
    )
    state["usage"] = _usage_since(llm, before)
    state["steps"] = result.steps
    state["trajectory"] = _rel_repo(run_dir / "trajectory.jsonl")
    if state["accepted"]:
        return state
    if result.status == "budget_exhausted":
        state["stop"] = True
        state["reason"] = state["reason"] or "budget exhausted"
        attempts.append(
            {"oracle": oracle, "attempt": state["attempts_used"], "accepted": False, "reason": "budget exhausted"}
        )
        return state
    if result.status == "abstained":
        text = str(result.final.get("reason") or "model abstained")
        state["parts"].append(f"model abstained: {text}")
        attempts.append({"oracle": oracle, "attempt": state["attempts_used"], "accepted": False, "reason": text})
        state["reason"] = "; ".join(part for part in state["parts"] if part)
        return state
    if result.status == "error":
        state["parts"].append(str(result.final.get("error") or "agent error"))
    elif not state["accepted"] and not state["reason"]:
        state["parts"].append(f"{oracle} not accepted")
    if not state["accepted"]:
        state["reason"] = "; ".join(part for part in state["parts"] if part) or state["reason"]
    return state


def _run_dir(llm, work: Path, name: str) -> Path:
    token = uuid.uuid4().hex[:8]
    folder = f"{name}-{token}"
    if getattr(llm, "model", "") == "deepseek-v4-pro":
        path = RUNS / folder
    else:
        path = work / "runs" / folder
    path.mkdir(parents=True, exist_ok=True)
    return path


def _last_trajectory(attempts: list[dict]) -> str | None:
    for record in reversed(attempts):
        path = record.get("trajectory")
        if path:
            return str(path)
    return None


def _usage_dict(usage: Usage) -> dict:
    return {
        "prompt_tokens": usage.prompt_tokens,
        "completion_tokens": usage.completion_tokens,
        "reasoning_tokens": usage.reasoning_tokens,
        "cache_hit_tokens": usage.cache_hit_tokens,
    }


def _base_meta(instance: Instance, llm, usage: Usage, cost: float, wall: float, trajectory: str | None) -> dict:
    return {
        "schema": "proofsmith.verifier/1",
        "system": "proofsmith",
        "instance_id": instance.id,
        "model": getattr(llm, "model", "") or "",
        "usage": _usage_dict(usage),
        "cost_usd": cost,
        "wall_s": wall,
        "trajectory": trajectory,
        "created_at": _now(),
    }


def _freeze_accept(sandbox, instance, llm, usage, cost, wall, accepted, out_dir: Path) -> Path:
    oracle = accepted["oracle"]
    variant = _ORACLE_VARIANT[oracle]
    spec = VARIANTS[variant]
    meta = _base_meta(instance, llm, usage, cost, wall, accepted.get("trajectory"))
    meta.update(
        {
            "status": "accepted",
            "abstain_reason": None,
            "oracle": oracle,
            "variant": variant,
            "signature": accepted.get("signature") or "",
            "runtime": {
                "n": RUNTIME_N,
                "k": RUNTIME_K,
                "fails": _fail_count(accepted),
                "signatures": _signature_counts(accepted),
            },
            "flags": {"cxxflags": spec.cxxflags, "ldflags": spec.ldflags, "env": dict(spec.env)},
        }
    )
    return freeze(sandbox.repo, meta, out_dir)


def _fail_count(accepted: dict) -> int:
    count = accepted.get("fail_count")
    if isinstance(count, int):
        return count
    return RUNTIME_N


def _signature_counts(accepted: dict) -> dict:
    counts = accepted.get("signatures")
    if isinstance(counts, dict):
        return counts
    signature = accepted.get("signature")
    if signature:
        return {signature: RUNTIME_K}
    return {}


def _freeze_abstain(sandbox, instance, llm, usage, cost, wall, reasons, trajectory, out_dir: Path) -> Path:
    _clear_harness(sandbox.repo)
    meta = _base_meta(instance, llm, usage, cost, wall, trajectory)
    meta.update(
        {
            "status": "abstained",
            "abstain_reason": "NO VERIFIER: " + "; ".join(reasons),
            "oracle": None,
            "variant": None,
            "signature": None,
            "runtime": {"n": 0, "k": RUNTIME_K, "fails": 0, "signatures": {}},
            "flags": {"cxxflags": "", "ldflags": "", "env": {}},
        }
    )
    return freeze(sandbox.repo, meta, out_dir)
