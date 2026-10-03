"""Run generated code with an explicit filesystem allowlist and no network."""
from __future__ import annotations

import os
import shutil
from pathlib import Path

SAFE_ENV = ("PATH", "HOME", "LANG", "LC_ALL", "USER", "LOGNAME", "TMPDIR")


def child_env(extra: dict | None = None) -> dict:
    value = {k: os.environ[k] for k in SAFE_ENV if k in os.environ}
    value.setdefault("LANG", "C.UTF-8")
    value.update(extra or {})
    return value


def isolated_command(command: list[str], cwd: Path, *, read: list[Path] = (), write: list[Path] = ()) -> list[str]:
    if not shutil.which("bwrap"):
        raise RuntimeError("bubblewrap is required for filesystem isolation; run scripts/setup_root.sh")
    cmd = ["bwrap", "--unshare-all", "--die-with-parent", "--new-session",
           "--proc", "/proc", "--dev", "/dev", "--tmpfs", "/tmp"]
    for name in ("/usr", "/bin", "/sbin", "/lib", "/lib64", "/etc"):
        if Path(name).exists():
            cmd.extend(["--ro-bind", name, name])
    # No host home, repository history, hidden dataset, or API credentials mount.
    for path in sorted({Path(p).resolve() for p in read}, key=lambda p: len(str(p))):
        if path.exists():
            cmd.extend(["--ro-bind", str(path), str(path)])
    for path in sorted({Path(p).resolve() for p in write}, key=lambda p: len(str(p))):
        if path.exists():
            cmd.extend(["--bind", str(path), str(path)])
    cmd.extend(["--chdir", str(cwd.resolve()), "bash", "-c",
                'ip link set lo up 2>/dev/null; exec "$@"', "proofsmith", *command])
    return cmd
