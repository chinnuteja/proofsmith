"""The seven tools shared by every system."""

from __future__ import annotations

from pathlib import Path

from proofsmith.config import RUN_TIMEOUT_S
from proofsmith.datasets.schema import BuildRecipe
from proofsmith.harness import compile_harness
from proofsmith.oracles.builds import BuildResult, build_variant
from proofsmith.oracles.runner import run_n
from proofsmith.sandbox import Sandbox

_VARIANTS = ("plain", "asan_ubsan", "tsan")

_SCHEMAS: list[dict] = [
    {
        "type": "function",
        "function": {
            "name": "run_shell",
            "description": (
                "Run a shell command with the sandbox repository as the working directory. "
                "The command cannot reach the network. Returns the exit code and truncated output."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "cmd": {"type": "string", "description": "Shell command to run."},
                    "timeout_s": {
                        "type": "integer",
                        "description": "Timeout in seconds. Defaults to 120.",
                    },
                },
                "required": ["cmd"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "read_file",
            "description": "Read a text file inside the sandbox repository and return numbered lines.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "Path relative to the repository root."},
                    "start_line": {"type": "integer", "description": "First line to return. Defaults to 1."},
                    "end_line": {"type": "integer", "description": "Last line to return. Defaults to 400."},
                },
                "required": ["path"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "write_file",
            "description": (
                "Write a file under proofsmith_harness/. "
                "Writes anywhere else are rejected and the tree is left unchanged."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "Path relative to the repository root."},
                    "content": {"type": "string", "description": "Full file contents."},
                },
                "required": ["path", "content"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "list_dir",
            "description": "List the entries in a directory inside the sandbox repository.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "Directory relative to the repository root. Defaults to the root.",
                    },
                },
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "build_variant",
            "description": (
                "Configure and build the repository with clang for one variant: "
                "plain, asan_ubsan, or tsan. Returns whether the build succeeded, "
                "the build directory, the last 60 log lines, and the compile_commands.json path."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "variant": {"type": "string", "enum": list(_VARIANTS)},
                },
                "required": ["variant"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "run_harness",
            "description": (
                "Compile proofsmith_harness/build.sh for one variant and run the harness "
                "up to 10 times. Returns each run's exit code, timeout flag, evidence kind, "
                "and signature, plus the first 60 lines of the first failing run."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "variant": {"type": "string", "enum": list(_VARIANTS)},
                    "n": {"type": "integer", "description": "Number of runs. Defaults to 1 and is capped at 10."},
                },
                "required": ["variant"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "finish",
            "description": "Stop successfully. Call this when the task is done.",
            "parameters": {
                "type": "object",
                "properties": {
                    "variant": {"type": "string", "enum": list(_VARIANTS)},
                    "summary": {"type": "string", "description": "The result the task asked for."},
                },
                "required": ["variant", "summary"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "abstain",
            "description": "Stop without a result and give the reason.",
            "parameters": {
                "type": "object",
                "properties": {
                    "reason": {"type": "string", "description": "Why the task cannot be finished."},
                },
                "required": ["reason"],
            },
        },
    },
]

_WRITE_DENIED = (
    "error: writes outside proofsmith_harness/ are not allowed. "
    "Only files under proofsmith_harness/ may be created, modified, or deleted."
)


class ToolSet:
    def __init__(self, sandbox: Sandbox, recipe: BuildRecipe, work: Path):
        self.sandbox = sandbox
        self.recipe = recipe
        self.work = Path(work)
        self.work.mkdir(parents=True, exist_ok=True)
        self.terminal: dict | None = None
        self.instance_id = ""
        self._builds: dict[str, BuildResult] = {}

    def schemas(self) -> list[dict]:
        return _SCHEMAS

    def dispatch(self, name: str, args: dict) -> str:
        handler = {
            "run_shell": self._run_shell,
            "read_file": self._read_file,
            "write_file": self._write_file,
            "list_dir": self._list_dir,
            "build_variant": self._build_variant,
            "run_harness": self._run_harness,
            "finish": self._finish,
            "abstain": self._abstain,
        }.get(name)
        if handler is None:
            return f"error: unknown tool {name}"
        try:
            return handler(args or {})
        except Exception as exc:
            return f"error: {type(exc).__name__}: {exc}"

    def _relative(self, path: str) -> Path | None:
        raw = Path(path)
        repo = self.sandbox.repo.resolve()
        candidate = raw.resolve() if raw.is_absolute() else (repo / raw).resolve()
        try:
            return candidate.relative_to(repo)
        except ValueError:
            return None

    def _run_shell(self, args: dict) -> str:
        cmd = args.get("cmd")
        if not isinstance(cmd, str) or not cmd:
            return "error: cmd must be a non-empty string"
        timeout = args.get("timeout_s", 120)
        try:
            timeout_s = int(timeout)
        except (TypeError, ValueError):
            return "error: timeout_s must be an integer"
        if timeout_s < 1:
            timeout_s = 1
        result = self.sandbox.exec(cmd, timeout_s)
        flag = "true" if result.timed_out else "false"
        return f"exit_code: {result.exit_code}\ntimed_out: {flag}\n{result.output}"

    def _read_file(self, args: dict) -> str:
        rel = self._relative(str(args.get("path", "")))
        if rel is None:
            return "error: path is outside the sandbox repository"
        path = self.sandbox.repo / rel
        if not path.is_file():
            return f"error: not a file: {rel.as_posix()}"
        start = _positive(args.get("start_line", 1), 1)
        end = _positive(args.get("end_line", 400), 400)
        if end < start:
            end = start
        lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
        chunk = lines[start - 1 : end]
        return "\n".join(f"{number}: {line}" for number, line in enumerate(chunk, start=start))

    def _write_file(self, args: dict) -> str:
        rel = self._relative(str(args.get("path", "")))
        if rel is None:
            return _WRITE_DENIED
        posix = rel.as_posix()
        if posix != "proofsmith_harness" and not posix.startswith("proofsmith_harness/"):
            return _WRITE_DENIED
        content = args.get("content")
        if not isinstance(content, str):
            return "error: content must be a string"
        path = self.sandbox.repo / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8", newline="\n")
        return f"wrote {posix} ({len(content)} bytes)"

    def _list_dir(self, args: dict) -> str:
        rel = self._relative(str(args.get("path", ".")))
        if rel is None:
            return "error: path is outside the sandbox repository"
        path = self.sandbox.repo / rel
        if not path.is_dir():
            return f"error: not a directory: {rel.as_posix()}"
        names = [child.name + ("/" if child.is_dir() else "") for child in path.iterdir()]
        return "\n".join(sorted(names)) if names else "(empty)"

    def _build_variant(self, args: dict) -> str:
        variant = args.get("variant")
        if variant not in _VARIANTS:
            return "error: variant must be plain, asan_ubsan, or tsan"
        result = build_variant(self.sandbox.repo, variant, self.recipe, self.work / "builds")
        self._builds[variant] = result
        log = ""
        if result.log_path.is_file():
            log = result.log_path.read_text(encoding="utf-8", errors="replace")
        tail = "\n".join(log.splitlines()[-60:])
        commands = str(result.compile_commands) if result.compile_commands else ""
        flag = "true" if result.ok else "false"
        return (
            f"ok: {flag}\n"
            f"build_dir: {result.build_dir}\n"
            f"compile_commands: {commands}\n"
            f"log:\n{tail}"
        )

    def _run_harness(self, args: dict) -> str:
        variant = args.get("variant")
        if variant not in _VARIANTS:
            return "error: variant must be plain, asan_ubsan, or tsan"
        try:
            requested = int(args.get("n", 1) or 1)
        except (TypeError, ValueError):
            return "error: n must be an integer"
        count = max(1, min(requested, 10))
        build = self._builds.get(variant)
        if build is None or not build.ok:
            built = self._build_variant({"variant": variant})
            build = self._builds.get(variant)
            if build is None or not build.ok:
                return "error: build failed\n" + built
        out_dir = self.work / "harness" / variant
        compiled = compile_harness(self.sandbox.repo, build, variant, out_dir)
        if not compiled.ok or compiled.binary is None:
            log = ""
            if compiled.log_path.is_file():
                log = compiled.log_path.read_text(encoding="utf-8", errors="replace")
            tail = "\n".join(log.splitlines()[-60:])
            return f"ok: false\nharness build failed\n{tail}"
        runs = run_n(
            compiled.binary,
            variant,
            count,
            RUN_TIMEOUT_S,
            self.sandbox.repo,
            str(self.sandbox.repo.resolve()),
            self.work / "harness-runs" / variant,
        )
        lines = [f"runs: {len(runs)}"]
        first_fail = None
        for run in runs:
            timed = "true" if run.timed_out else "false"
            lines.append(
                f"run {run.index}: exit={run.exit_code} timed_out={timed} "
                f"kind={run.evidence.kind} signature={run.evidence.signature}"
            )
            if first_fail is None and (run.timed_out or run.exit_code != 0):
                first_fail = run
        if first_fail is not None:
            output = Path(first_fail.output_path).read_text(encoding="utf-8", errors="replace")
            lines.append("first_failure:")
            lines.append("\n".join(output.splitlines()[:60]))
        return "\n".join(lines)

    def _finish(self, args: dict) -> str:
        variant = args.get("variant")
        summary = args.get("summary")
        if variant not in _VARIANTS or not isinstance(summary, str):
            return "error: finish requires variant (plain, asan_ubsan, or tsan) and a summary string"
        self.terminal = {"tool": "finish", "variant": variant, "summary": summary}
        return "finished"

    def _abstain(self, args: dict) -> str:
        reason = args.get("reason")
        if not isinstance(reason, str) or not reason.strip():
            return "error: abstain requires a reason string"
        self.terminal = {"tool": "abstain", "reason": reason}
        return "abstained"


def _positive(value: object, default: int) -> int:
    try:
        number = int(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return default
    return number if number >= 1 else default
