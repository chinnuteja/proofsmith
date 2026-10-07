"""Build a static, account-free results site from the verified evaluation kit."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import zipfile

ROOT = Path(__file__).resolve().parents[1]
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("--out", type=Path, required=True)
args = parser.parse_args()
out = args.out.resolve()
if out == ROOT or out.is_relative_to(ROOT / ".git"):
    raise ValueError("output must be a separate directory")
out.mkdir(parents=True, exist_ok=False)
kit = ROOT / "artifacts/proofsmith-byteask-evaluation-kit.zip"
record = json.loads((ROOT / "results/byteask-comparison-package.json").read_text())
assert hashlib.sha256(kit.read_bytes()).hexdigest() == record["sha256"]
reproduction = json.loads((ROOT / "results/byteask-comparison-reproduction.json").read_text())
assert reproduction["archive_sha256"] == record["sha256"]
assert reproduction["retained_live_candidates_independently_rescored"]
with zipfile.ZipFile(kit) as archive:
    for item in archive.namelist():
        if not item.startswith(("experiments/byteask-comparison/", "docs/", "results/")):
            continue
        target = (out / item).resolve()
        if not target.is_relative_to(out):
            raise ValueError("archive path escapes site")
        archive.extract(item, out)
for relative in ("index.html", "results/byteask-comparison-package.json", "results/byteask-comparison-reproduction.json"):
    target = out / relative
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(ROOT / relative, target)
(out / "artifacts").mkdir(exist_ok=True)
shutil.copyfile(kit, out / "artifacts" / kit.name)
(out / ".nojekyll").write_text("")
print(json.dumps({"site": str(out), "kit_sha256": record["sha256"], "model_requests": 0}))
