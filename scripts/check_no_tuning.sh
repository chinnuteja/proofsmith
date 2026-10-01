#!/usr/bin/env bash
set -euo pipefail
cd ~/proofsmith
python3 - << 'PY'
import json
import pathlib
import sys

root = pathlib.Path(".")
needles: set[str] = set()

def take(value) -> None:
    if isinstance(value, str) and len(value) >= 3:
        needles.add(value)
    elif isinstance(value, list):
        for item in value:
            take(item)

hidden_dirs = []
for base in (root / "cases", root / "data"):
    if base.is_dir():
        hidden_dirs.extend(p for p in base.rglob("*.json") if "hidden" in p.parts)

for path in hidden_dirs:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        print(f"check_no_tuning: FAIL unreadable {path}")
        sys.exit(1)

    def walk(obj) -> None:
        if isinstance(obj, dict):
            take(obj.get("id"))
            take(obj.get("fix_files"))
            for key in ("function", "functions", "function_names"):
                if key in obj:
                    take(obj[key])
            for value in obj.values():
                walk(value)
        elif isinstance(obj, list):
            for item in obj:
                walk(item)

    walk(data)

files: list[pathlib.Path] = []
prompts = root / "proofsmith" / "prompts"
if prompts.is_dir():
    files.extend(p for p in prompts.rglob("*") if p.is_file())
pipeline = root / "proofsmith" / "pipeline.py"
if pipeline.is_file():
    files.append(pipeline)

if not needles or not files:
    print("check_no_tuning: OK")
    sys.exit(0)

hits: list[str] = []
for path in files:
    text = path.read_text(encoding="utf-8", errors="replace")
    for needle in sorted(needles):
        if needle in text:
            hits.append(f"{path}: {needle}")

if hits:
    print("check_no_tuning: FAIL")
    print("\n".join(hits))
    sys.exit(1)

print("check_no_tuning: OK")
PY
