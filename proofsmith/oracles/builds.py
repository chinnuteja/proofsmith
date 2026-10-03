"""Configure and build a tree for one compiler variant."""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path

from proofsmith.config import WORK
from proofsmith.datasets.schema import BuildRecipe
from proofsmith.oracles.variants import VARIANTS


@dataclass
class BuildResult:
    ok: bool
    build_dir: Path
    compile_commands: Path | None
    log_path: Path
    duration_s: float


def snapshot_sha256(repo: Path) -> str:
    root = Path(repo).resolve()
    rows: list[str] = []
    for path in sorted(root.rglob("*")):
        rel = path.relative_to(root).as_posix()
        if rel == ".git" or rel.startswith(".git/") or rel.startswith("proofsmith_harness/"):
            continue
        if path.is_symlink():
            digest = "symlink:" + os.readlink(path)
        elif path.is_file():
            digest = hashlib.sha256(path.read_bytes()).hexdigest()
        else:
            continue
        rows.append(f"{rel}\t{digest}")
    payload = "\n".join(rows) + ("\n" if rows else "")
    return hashlib.sha256(payload.encode()).hexdigest()


def _needs_stage(repo: Path) -> bool:
    resolved = repo.resolve()
    text = str(resolved)
    try:
        under_work = resolved.is_relative_to(WORK.resolve())
    except ValueError:
        under_work = False
    return (not under_work) or (" " in text) or text.startswith("/mnt/")


def _source_dir(repo: Path, tree_hash: str) -> Path:
    if not _needs_stage(repo):
        return repo.resolve()
    staged = WORK / "cache" / "src" / tree_hash[:16]
    marker = staged / ".proofsmith-src"
    if marker.is_file() and marker.read_text(encoding="utf-8").strip() == tree_hash:
        return staged
    if staged.exists():
        shutil.rmtree(staged)
    shutil.copytree(repo, staged, ignore=shutil.ignore_patterns(".git"))
    marker.write_text(tree_hash + "\n", encoding="utf-8", newline="\n")
    return staged


def _log(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8", newline="\n") as handle:
        handle.write(text)
        if text and not text.endswith("\n"):
            handle.write("\n")


def _run(cmd: list[str], cwd: Path, log_path: Path, env: dict[str, str] | None = None) -> int:
    from proofsmith.isolation import child_env

    _log(log_path, "$ " + " ".join(cmd))
    proc = subprocess.run(
        cmd,
        cwd=cwd,
        env=env if env is not None else child_env(),
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        check=False,
        text=True,
    )
    _log(log_path, proc.stdout)
    return proc.returncode


def _link_build(dest: Path, cache: Path) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    if dest.is_symlink() or dest.exists():
        if dest.is_symlink() or dest.is_file():
            dest.unlink()
        else:
            shutil.rmtree(dest)
    dest.symlink_to(cache, target_is_directory=True)


def build_key(repo: Path, variant: str, recipe: BuildRecipe, src: Path | None = None) -> str:
    from proofsmith.config import REPO

    tree_hash = snapshot_sha256(repo)
    src = src or _source_dir(repo, tree_hash)
    script_hash = None
    if recipe.custom_script:
        script = Path(recipe.custom_script)
        script = script if script.is_absolute() else REPO / script
        script_hash = hashlib.sha256(script.read_bytes()).hexdigest() if script.is_file() else "missing"
    spec = VARIANTS[variant]
    inputs = {"tree": tree_hash, "source": str(src.resolve()), "recipe": recipe.model_dump(),
              "script": script_hash, "flags": spec.cxxflags, "ldflags": spec.ldflags, "variant": variant}
    return hashlib.sha256(json.dumps(inputs, sort_keys=True).encode()).hexdigest()[:32] + "-" + variant


def build_variant(repo: Path, variant: str, recipe: BuildRecipe, out_root: Path) -> BuildResult:
    started = time.monotonic()
    spec = VARIANTS[variant]
    tree_hash = snapshot_sha256(repo)
    src = _source_dir(repo, tree_hash)
    # The source directory is part of the key. A content-only cache reused objects
    # whose debug paths lived in a different tree, so the report had no app frames.
    cache = WORK / "cache" / "builds" / build_key(repo, variant, recipe, src)
    log_path = cache / "build.log"
    dest = Path(out_root) / variant
    commands = cache / "compile_commands.json"
    marker = cache / ".proofsmith-ok"

    if marker.is_file() and commands.is_file():
        _link_build(dest, cache)
        return BuildResult(True, dest, dest / "compile_commands.json", log_path, time.monotonic() - started)

    if cache.exists():
        shutil.rmtree(cache)
    cache.mkdir(parents=True)
    from proofsmith.isolation import child_env

    env = child_env()
    ok = False
    if recipe.system == "cmake":
        configure = [
            "cmake",
            "-S",
            str(src),
            "-B",
            str(cache),
            "-G",
            "Ninja",
            "-DCMAKE_C_COMPILER=clang",
            "-DCMAKE_CXX_COMPILER=clang++",
            "-DCMAKE_BUILD_TYPE=",
            f"-DCMAKE_C_FLAGS={spec.cxxflags}",
            f"-DCMAKE_CXX_FLAGS={spec.cxxflags}",
            f"-DCMAKE_EXE_LINKER_FLAGS={spec.ldflags}",
            f"-DCMAKE_SHARED_LINKER_FLAGS={spec.ldflags}",
            "-DCMAKE_EXPORT_COMPILE_COMMANDS=ON",
            *recipe.cmake_args,
        ]
        build = ["cmake", "--build", str(cache), "-j", str(recipe.jobs)]
        for target in recipe.targets:
            build.extend(["--target", target])
        ok = _run(configure, src, log_path) == 0 and _run(build, src, log_path) == 0
    elif recipe.system == "make":
        cmd = [
            "make",
            f"-j{recipe.jobs}",
            "CC=clang",
            "CXX=clang++",
            f"CFLAGS={spec.cxxflags}",
            f"CXXFLAGS={spec.cxxflags}",
            f"LDFLAGS={spec.ldflags}",
        ]
        ok = _run(cmd, src, log_path) == 0
    elif recipe.system == "custom":
        if not recipe.custom_script:
            _log(log_path, "custom build has no script\n")
            ok = False
        else:
            child = env
            child["PS_REPO"] = str(src)
            child["PS_BUILD_DIR"] = str(cache)
            child["PS_CC"] = "clang"
            child["PS_CXX"] = "clang++"
            child["PS_CXXFLAGS"] = spec.cxxflags
            child["PS_LDFLAGS"] = spec.ldflags
            child["PS_VARIANT"] = variant
            script = recipe.custom_script
            if not Path(script).is_absolute():
                from proofsmith.config import REPO

                script = str((REPO / script).resolve())
            ok = _run(["bash", script], src, log_path, child) == 0
    else:
        _log(log_path, f"unknown build system {recipe.system}\n")

    duration = time.monotonic() - started
    if not ok or not commands.is_file():
        return BuildResult(False, cache, commands if commands.is_file() else None, log_path, duration)
    marker.write_text(tree_hash + "\n", encoding="utf-8", newline="\n")
    _link_build(dest, cache)
    return BuildResult(True, dest, dest / "compile_commands.json", log_path, duration)
