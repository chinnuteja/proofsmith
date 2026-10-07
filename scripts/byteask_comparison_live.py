"""Collect one real ByteAsk candidate per case inside an outer filesystem allowlist.

Only an already granted Pro/Free allowance with zero prepaid extra credit is used.
This collector never purchases, upgrades, tops up, or uses a fallback provider.
"""
from __future__ import annotations
import argparse
from datetime import datetime, timezone
import difflib
import json
import os
from pathlib import Path
import re
import shutil
import signal
import subprocess
import sys
import tempfile
import time
import tomllib
import urllib.request

sys.path.insert(0, str(Path(__file__).resolve().parent))
from byteask_comparison import CASE_IDS, ROOT, config, digest, dump, validate
from proofsmith.gate import _copy_source
from proofsmith.isolation import child_env

MODEL = "gpt-5.4"
PROVIDER = "byteask"
BASE_URL = "https://code.byteask.ai/byteask/v1"
BINARY = ROOT / ".tools/byteask/byteask-engine"
ACCOUNT = ROOT / ".tools/byteask-home"
MAX_TURNS = 20
MAX_WALL_S = 600
PROMPT = """Fix the C++ bug described in issue.md. Keep the public API and normal behavior.
Only change subject.cpp; subject.h, smoke.cpp, CMakeLists.txt and supplied/ are trusted test inputs.
You may create temporary build outputs or additional local tests. Investigate and verify normally.
Use your available native C/C++ sanitizer, debugging, analysis and build/test tools when useful.
The supplied regression can be compiled with:
clang++ -std=c++17 -O0 -g -I. -Isupplied supplied/harness.cpp subject.cpp -o regression && ./regression
Name each tool you call and quote its key output. Do not read account/configuration files or other workspaces.
Do not use web search, other agents, online compiler services or a fallback provider.
End your final response with exactly one of these markers on its own last line:
BYTEASK_ACCEPTED if you consider the patch ready after verification;
BYTEASK_UNRESOLVED if you cannot confidently finish and verify it.
"""


def managed_config():
    text = (ACCOUNT / "config.toml").read_text()
    cfg = tomllib.loads(text)
    provider = cfg.get("model_providers", {}).get(PROVIDER, {})
    if cfg.get("model_provider") != PROVIDER or provider.get("base_url", "").rstrip("/") != BASE_URL:
        raise RuntimeError("use the official managed ByteAsk profile; no fallback provider allowed")
    token = provider.get("experimental_bearer_token")
    if not token:
        raise RuntimeError("ByteAsk sign-in is required")
    return text, cfg, token


def account_status(token):
    req = urllib.request.Request(BASE_URL + "/usage", headers={"Authorization": "Bearer " + token})
    with urllib.request.urlopen(req, timeout=15) as response:
        data = json.load(response)
    keys = ("plan", "extra_balance_usd", "extra_granted_usd", "extra_spent_usd",
            "used_5h_pct", "used_week_pct", "reset_5h_sec", "reset_week_sec")
    return {key: data.get(key) for key in keys}


def quota_guard(status):
    if status["plan"] not in {"free", "pro"}:
        raise RuntimeError("unrecognized existing allowance; stop before model requests")
    if status["extra_balance_usd"] != 0 or status["extra_spent_usd"] != 0:
        raise RuntimeError("do not use extra/prepaid credit in this zero-spend test")
    for key in ("used_5h_pct", "used_week_pct"):
        value = status[key]
        if not isinstance(value, (float, int)) or not 0 <= value < 50:
            raise RuntimeError("stop with ample allowance remaining; no paid fallback")


def box(command, candidate, home):
    """Share network for the model; mount no experiment, evaluator or host home."""
    if not shutil.which("bwrap"):
        raise RuntimeError("bubblewrap is required")
    cmd = ["bwrap", "--unshare-all", "--share-net", "--die-with-parent", "--new-session",
           "--proc", "/proc", "--dev", "/dev", "--tmpfs", "/tmp"]
    for name in ("/usr", "/bin", "/sbin", "/lib", "/lib64", "/etc"):
        if Path(name).exists():
            cmd += ["--ro-bind", name, name]
    # WSL's resolv.conf can point outside /etc. Preserve only its resolved file.
    resolved = Path("/etc/resolv.conf").resolve()
    if not resolved.is_relative_to(Path("/etc")):
        cmd += ["--ro-bind", str(resolved), str(resolved)]
    cmd += ["--ro-bind", str(BINARY.parent), str(BINARY.parent),
            "--bind", str(home), str(home), "--bind", str(candidate), str(candidate),
            "--chdir", str(candidate), *command]
    return cmd


def private_profile(text, cfg, home):
    home.mkdir()
    catalog = cfg.get("model_catalog_json")
    if catalog:
        source = Path(catalog)
        shutil.copyfile(source, home / "models-catalog.json")
        text = re.sub(r'^model_catalog_json\s*=.*$',
                      'model_catalog_json = ' + json.dumps(str(home / 'models-catalog.json')),
                      text, flags=re.MULTILINE)
    (home / "config.toml").write_text(text)
    (home / "config.toml").chmod(0o600)


def isolated_env(home):
    return child_env({"HOME": str(home.parent), "BYTEASK_HOME": str(home),
                      "BYTEASK_BRAND": "ByteAsk", "BYTEASK_NO_UPDATE_CHECK": "1",
                      "BYTEASK_REPORTED_VERSION": "0.1.15", "DEEPSEEK_API_KEY": ""})


def check_isolation(experiment):
    validate(experiment)
    text, cfg, token = managed_config()
    config.WORK.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="byteask-isolation-", dir=config.WORK) as name:
        work = Path(name)
        candidate, home = work / "candidate", work / "home"
        _copy_source(experiment / "cases" / CASE_IDS[0] / "original", candidate)
        private_profile(text, cfg, home)
        probe = ("test ! -e \"$1/cases/quota-overflow/hidden/judge.cpp\" && "
                 "test ! -e \"$1/cases/quota-overflow/controls/fixed.cpp\" && "
                 "test ! -e \"$2/docs/protocol.json\" && "
                 "test ! -e \"$3/.cache\" && test -f subject.cpp && "
                 "clang++ --version >/dev/null && \"$4\" --version")
        command = ["bash", "-c", probe, "probe", str(experiment), str(ROOT), str(Path.home()), str(BINARY)]
        result = subprocess.run(box(command, candidate, home), env=isolated_env(home),
                                capture_output=True, text=True, timeout=30)
        if result.returncode != 0:
            raise RuntimeError(f"outer isolation probe failed (exit {result.returncode})")
    record = {"schema": "proofsmith.byteask-live-isolation/1", "hidden_judge_accessible": False,
              "authored_fixes_accessible": False, "repository_accessible": False,
              "host_home_accessible": False, "compiler_accessible": True,
              "byteask_binary_accessible": True, "model_calls": 0}
    print(json.dumps(record, indent=2))
    return record


def marker(final):
    lines = [line.strip() for line in final.splitlines() if line.strip()]
    if not lines or lines[-1] not in {"BYTEASK_ACCEPTED", "BYTEASK_UNRESOLVED"}:
        return "UNRESOLVED"
    if len([line for line in lines if line in {"BYTEASK_ACCEPTED", "BYTEASK_UNRESOLVED"}]) != 1:
        return "UNRESOLVED"
    return "ACCEPTED" if lines[-1] == "BYTEASK_ACCEPTED" else "UNRESOLVED"


def collect(experiment, out):
    validate(experiment)
    text, cfg, token = managed_config()
    before = account_status(token)
    quota_guard(before)
    isolation = check_isolation(experiment)
    out.mkdir(parents=True, exist_ok=False)
    catalog = json.loads(Path(cfg["model_catalog_json"]).read_text())
    with urllib.request.urlopen(urllib.request.Request(BASE_URL + "/model-access",
         headers={"Authorization": "Bearer " + token}), timeout=15) as response:
        access = json.load(response)
    if MODEL in access.get("locked", []) or MODEL in access.get("inactive", []):
        raise RuntimeError("selected model unavailable; no model fallback allowed")
    lock = {"schema": "proofsmith.byteask-execution-lock/1", "frozen_at": datetime.now(timezone.utc).isoformat(),
            "protocol_sha256": digest(experiment / "protocol.json"), "collector_sha256": digest(Path(__file__)),
            "binary_sha256": digest(BINARY), "model": MODEL, "provider": PROVIDER,
            "max_turns_per_case": MAX_TURNS, "max_wall_s_per_case": MAX_WALL_S,
            "max_additional_spend_usd": 0, "account_usage_before": before,
            "prompt": PROMPT, "case_order": CASE_IDS, "outer_isolation": isolation,
            "selection": "first and only attempt per case; no silent retries"}
    dump(out / "execution-lock.json", lock)
    observations = []
    config.WORK.mkdir(parents=True, exist_ok=True)
    stop_reason = None
    for case_id in CASE_IDS:
        print(f"ByteAsk model run: {case_id}", flush=True)
        try:
            before_case = account_status(token)
            quota_guard(before_case)
        except Exception as exc:
            stop_reason = f"account allowance check failed: {type(exc).__name__}"
            break
        case = experiment / "cases" / case_id
        evidence = out / case_id
        evidence.mkdir()
        status, reason, returncode = "UNRESOLVED", None, None
        start = time.monotonic()
        with tempfile.TemporaryDirectory(prefix="byteask-live-", dir=config.WORK) as name:
            work = Path(name)
            candidate, home = work / "candidate", work / "home"
            _copy_source(case / "original", candidate)
            shutil.copytree(case / "supplied", candidate / "supplied")
            shutil.copyfile(ROOT / "proofsmith/runtime/proofsmith_check.h", candidate / "supplied/proofsmith_check.h")
            private_profile(text, cfg, home)
            command = [str(BINARY), "exec", "--json", "--ephemeral", "--sandbox", "workspace-write",
                       "--skip-git-repo-check", "--color", "never", "--max-turns", str(MAX_TURNS),
                       "-m", MODEL, "-c", 'mcp_servers={}', "-c", 'approval_policy="never"',
                       "-c", 'web_search="disabled"',
                       "-o", str(home / "final.txt"), "-"]
            with (evidence / "byteask.jsonl").open("w") as stdout, (evidence / "byteask.stderr").open("w") as stderr:
                process = subprocess.Popen(box(command, candidate, home), env=isolated_env(home),
                                           stdin=subprocess.PIPE, text=True, stdout=stdout, stderr=stderr,
                                           start_new_session=True)
                try:
                    process.communicate(PROMPT, timeout=MAX_WALL_S)
                    returncode = process.returncode
                except subprocess.TimeoutExpired:
                    os.killpg(process.pid, signal.SIGTERM)
                    try:
                        process.communicate(timeout=5)
                    except subprocess.TimeoutExpired:
                        os.killpg(process.pid, signal.SIGKILL)
                        process.communicate()
                    reason = "wall-time limit reached"
            final_path = home / "final.txt"
            final = final_path.read_text() if final_path.is_file() else ""
            # Never put managed credentials in portable evidence.
            leaked = token in final
            for path in (evidence / "byteask.jsonl", evidence / "byteask.stderr"):
                content = path.read_text()
                if token in content:
                    leaked = True
                    path.write_text(content.replace(token, "[REDACTED_CREDENTIAL]"))
            final = final.replace(token, "[REDACTED_CREDENTIAL]")
            (evidence / "final.txt").write_text(final)
            snapshot = evidence / "candidate"
            _copy_source(case / "original", snapshot)
            protected_changed = []
            for original in (case / "original").iterdir():
                if original.name == "subject.cpp":
                    continue
                proposed = candidate / original.name
                if proposed.is_symlink() or not proposed.is_file() or proposed.read_bytes() != original.read_bytes():
                    protected_changed.append(original.name)
            for original in (candidate / "supplied").rglob("*"):
                if original.is_symlink():
                    protected_changed.append("supplied symlink")
            for original in (case / "supplied").iterdir():
                proposed = candidate / "supplied" / original.name
                if not proposed.is_file() or proposed.is_symlink() or proposed.read_bytes() != original.read_bytes():
                    protected_changed.append("supplied/" + original.name)
            runtime = candidate / "supplied/proofsmith_check.h"
            if not runtime.is_file() or runtime.is_symlink() or runtime.read_bytes() != (ROOT / "proofsmith/runtime/proofsmith_check.h").read_bytes():
                protected_changed.append("supplied/proofsmith_check.h")
            proposed = candidate / "subject.cpp"
            if proposed.is_file() and not proposed.is_symlink():
                content = proposed.read_text()
                if token in content:
                    leaked = True
                (snapshot / "subject.cpp").write_text(content.replace(token, "[REDACTED_CREDENTIAL]"))
            else:
                protected_changed.append("subject.cpp missing or symlink")
            if returncode == 0 and not protected_changed and not leaked:
                status = marker(final)
            elif protected_changed:
                reason = "protected input changed: " + ", ".join(protected_changed)
            elif leaked:
                reason = "credential appeared in output; redacted and run unresolved"
            elif reason is None:
                reason = f"ByteAsk process exited {returncode}"
            diff = ''.join(difflib.unified_diff((case / 'original/subject.cpp').read_text().splitlines(True),
                                               (snapshot / 'subject.cpp').read_text().splitlines(True),
                                               fromfile='original/subject.cpp', tofile='candidate/subject.cpp'))
            (evidence / "candidate.diff").write_text(diff)
        wall = time.monotonic() - start
        try:
            after_case = account_status(token)
            quota_guard(after_case)
        except Exception as exc:
            after_case = None
            stop_reason = f"post-run allowance check failed: {type(exc).__name__}"
        trace = evidence / "byteask.jsonl"
        observation = {"case_id": case_id, "origin": "byteask_model", "candidate_path": str(snapshot),
                       "claimed_status": status, "reason": reason, "patcher_exit_code": returncode,
                       "model": MODEL, "provider": PROVIDER, "protocol_sha256": lock["protocol_sha256"],
                       "transcript_path": str(trace), "transcript_sha256": digest(trace), "wall_s": wall,
                       "account_usage": {"before": before_case, "after": after_case,
                                         "additional_purchase_usd": 0, "per_case_dollar_cost": None},
                       "execution_lock_sha256": digest(out / "execution-lock.json")}
        observations.append(observation)
        dump(out / "observations.json", observations)
        print(json.dumps({"case_id": case_id, "claimed_status": status, "exit_code": returncode, "wall_s": round(wall, 2)}), flush=True)
        if returncode != 0 and stop_reason is None:
            stop_reason = "ByteAsk execution error; stop collection rather than repeat a broken setup"
        if stop_reason or reason == "credential appeared in output; redacted and run unresolved":
            break
    dump(out / "collection.json", {"observations": len(observations), "expected": 5,
                                   "stop_reason": stop_reason, "additional_purchase_usd": 0,
                                   "complete": len(observations) == 5})


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--experiment", type=Path, default=ROOT / "experiments/byteask-comparison/v1")
    parser.add_argument("--out", type=Path)
    parser.add_argument("--isolation-check", action="store_true")
    args = parser.parse_args()
    if args.isolation_check:
        check_isolation(args.experiment.resolve())
    elif args.out:
        collect(args.experiment.resolve(), args.out.resolve())
    else:
        parser.error("supply --isolation-check or a fresh --out directory")
