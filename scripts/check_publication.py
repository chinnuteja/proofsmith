"""Audit staged/history blobs without printing private credentials or file contents."""
import hashlib
import json
from pathlib import Path
import re
import subprocess
import tomllib
from dotenv import dotenv_values

ROOT = Path(__file__).resolve().parents[1]
secrets = [v.encode() for k, v in dotenv_values(ROOT / ".env").items()
           if v and any(x in k.upper() for x in ("KEY", "TOKEN", "SECRET")) and len(v) >= 16]
private = ROOT / ".tools/byteask-home/config.toml"
if private.is_file():
    cfg = tomllib.loads(private.read_text())
    token = cfg.get("model_providers", {}).get("byteask", {}).get("experimental_bearer_token")
    if token:
        secrets.append(token.encode())

def git(*args):
    return subprocess.check_output(["git", *args], cwd=ROOT)

entries = {}
for line in git("ls-files", "--stage", "-z").split(b"\0"):
    if not line:
        continue
    metadata, name = line.split(b"\t", 1)
    mode, identity, stage = metadata.split()
    path = name.decode()
    if stage != b"0" or mode == b"120000":
        raise ValueError("unmerged input or source symlink")
    if any(part in (".tools", ".env", "runs", "scratch", ".git") for part in Path(path).parts):
        raise ValueError("private/runtime file staged")
    entries[path] = identity.decode()
requests = set(entries.values())
for line in git("rev-list", "--objects", "--all").splitlines():
    requests.add(line.split(b" ", 1)[0].decode())
data = subprocess.check_output(["git", "cat-file", "--batch"], input=("\n".join(sorted(requests)) + "\n").encode(), cwd=ROOT)
blobs = {}
position = 0
patterns = (rb"gh[pousr]_[A-Za-z0-9]{30,}", rb"github_pat_[A-Za-z0-9_]{50,}", rb"sk-[A-Za-z0-9]{28,}")
while position < len(data):
    end = data.index(b"\n", position)
    identity, kind, length = data[position:end].split()
    size = int(length)
    content = data[end + 1:end + 1 + size]
    position = end + 1 + size + 1
    if kind != b"blob":
        continue
    if any(secret in content for secret in secrets) or any(re.search(pattern, content) for pattern in patterns):
        # The digest identifies a blob for local investigation, not its contents.
        raise ValueError("credential-like bytes in publication blob " + identity.decode())
    blobs[identity.decode()] = content

protocols = [json.loads((ROOT / "docs/protocol.json").read_text()),
             json.loads((ROOT / "experiments/byteask-comparison/v1/protocol.json").read_text())]
expected = dict(protocols[0]["files"])
expected.update(protocols[1]["implementation_hashes"])
expected.update({"experiments/byteask-comparison/v1/cases/" + k: v for k,v in protocols[1]["asset_hashes"].items()})
for relative, identity in expected.items():
    if relative not in entries or hashlib.sha256(blobs[entries[relative]]).hexdigest() != identity:
        raise ValueError("staged frozen input differs: " + relative)
for case in json.loads((ROOT / "experiments/byteask-comparison/live-v1/observations.json").read_text()):
    relative = "experiments/byteask-comparison/live-v1/" + case["case_id"] + "/byteask.jsonl"
    assert hashlib.sha256(blobs[entries[relative]]).hexdigest() == case["transcript_sha256"]
record = {"staged_files": len(entries), "history_and_staged_blobs_scanned": len(blobs),
          "credential_scan_passed": True, "private_paths_excluded": True,
          "staged_frozen_hashes_match": True, "staged_live_trace_hashes_match": True}
print(json.dumps(record, indent=2))
(ROOT / "results/publication-audit.json").write_text(json.dumps(record, indent=2) + "\n")
