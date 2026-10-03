"""Export data and a runnable evaluator; hidden answers stay out of the visible split."""
from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

from proofsmith import config
from proofsmith.datasets.mine import mirror_path
from proofsmith.datasets.schema import HiddenInstance, Instance
from proofsmith.eval.runner import atomic_json
from proofsmith.freeze import load_bundle
from proofsmith.isolation import child_env


def export_benchmark(dest: Path) -> Path:
    dest = dest.resolve()
    if dest == config.REPO.resolve() or config.REPO.resolve().is_relative_to(dest):
        raise ValueError("export destination must not contain the source project")
    dest.mkdir(parents=True, exist_ok=True)
    for name in ("proofsmith", "config"):
        target = dest / name
        if target.exists():
            shutil.rmtree(target)
        shutil.copytree(config.REPO / name, target, ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
    shutil.copy2(config.REPO / "pyproject.toml", dest / "pyproject.toml")
    scripts = dest / "scripts"
    scripts.mkdir(exist_ok=True)
    for path in (config.REPO / "scripts").glob("*build*.sh"):
        shutil.copy2(path, scripts / path.name)
    records = []
    licenses = {}
    root = config.REPO / "data/trackB"
    for path in sorted((root / "instances").glob("*.json")):
        instance = Instance.model_validate_json(path.read_text())
        hidden = HiddenInstance.model_validate_json((root / "hidden" / path.name).read_text())
        # Source metadata only. Repository contents are fetched at the pinned commits.
        for sub in ("instances", "hidden"):
            target = dest / "data/trackB" / sub
            target.mkdir(parents=True, exist_ok=True)
            shutil.copy2(root / sub / path.name, target / path.name)
        diff = root / "hidden" / f"{instance.id}.fix.diff"
        if diff.exists():
            shutil.copy2(diff, dest / "data/trackB/hidden" / diff.name)
        records.append({"id": instance.id, "repo": instance.source.url, "buggy_commit": instance.source.commit})
        url = instance.source.url or ""
        if url not in licenses:
            repo = mirror_path(url)
            found = []
            for candidate in ("LICENSE", "LICENSE.txt", "LICENSE.md", "LICENSE-MIT", "COPYING"):
                result = subprocess.run(["git", "-C", str(repo), "show", f"{instance.source.commit}:{candidate}"],
                    capture_output=True, text=True, check=False, timeout=15,
                    env=child_env({"GIT_NO_LAZY_FETCH": "1"}))
                if result.returncode == 0:
                    name = repo.stem + "-" + candidate
                    license_dir = dest / "licenses"
                    license_dir.mkdir(exist_ok=True)
                    (license_dir / name).write_text(result.stdout)
                    found.append({"source_path": candidate, "copy": "licenses/" + name})
            licenses[url] = {"commit": instance.source.commit, "files": found,
                             "status": "license files preserved" if found else "needs license review before publishing"}
    for name in ("EXCLUDED.md", "REJECTED.md"):
        if (root / name).exists():
            shutil.copy2(root / name, dest / "data/trackB" / name)
    artifacts = []
    for bundle in sorted((config.RESULTS / "eval").rglob("verifier.json")):
        meta = load_bundle(bundle.parent)
        if meta["instance_id"] not in {r["id"] for r in records}:
            continue
        rel = bundle.parent.relative_to(config.RESULTS / "eval")
        target = dest / "results/eval" / rel
        if target.exists():
            shutil.rmtree(target)
        shutil.copytree(bundle.parent, target)
        verdict = bundle.parent.with_suffix(".json")
        if verdict.exists():
            shutil.copy2(verdict, target.with_suffix(".json"))
        artifacts.append({"path": target.relative_to(dest).as_posix(), "system": meta["system"],
                          "instance_id": meta["instance_id"], "exploratory": "protocol_sha256" not in meta})
    atomic_json(dest / "manifest.json", {"schema": "proofsmith.benchmark/1", "instances": records,
                "bundles": artifacts, "licenses": licenses, "hidden_split": "data/trackB/hidden"})
    (dest / "LICENSES.md").write_text("# Upstream license inventory\n\nSource code is fetched from pinned upstream commits; it is not included here. Original license files available locally are preserved in `licenses/`. Each entry in `manifest.json` records its source commit. Missing license files require review before publishing. The dataset contains issue text and fix diffs; do not treat this inventory as a blanket license for that material.\n")
    (dest / "README.md").write_text("""# C/C++ reproduction benchmark

Visible inputs: `data/trackB/instances/`. Hidden evaluator answers: `data/trackB/hidden/`.
Keep the hidden split outside the agent's filesystem. The excluded instance is documented in `data/trackB/EXCLUDED.md`.
Historical bundles are explicitly marked exploratory in `manifest.json`; they do not establish comparative performance.

Install the package from this directory in Linux/WSL with the documented clang, LLVM, CMake, Ninja, ctags and bubblewrap dependencies:

```bash
python -m pip install -e .
proofsmith evaluate --bundle results/eval/B/spdlog-1570/b1 \\
  --instance data/trackB/instances/spdlog-1570.json \\
  --hidden data/trackB/hidden/spdlog-1570.json --out verdict.json
```

No model key is needed. The first source checkout may require internet access; subsequent runs use the local mirror.
Inspect the per-repository license inventory before distributing source, issue text, or diffs.
""", encoding="utf-8")
    return dest
