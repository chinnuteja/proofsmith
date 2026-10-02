#!/usr/bin/env bash
set -euo pipefail
cd ~/proofsmith
source ~/.venvs/proofsmith/bin/activate

python3 - << 'PY'
import json
import sys
from collections import Counter
from pathlib import Path

root = Path("data/trackB")
visible = sorted((root / "instances").glob("*.json"))
if len(visible) < 10:
    print(f"instances={len(visible)} below floor 10")
    sys.exit(1)
counts = Counter()
repos = Counter()
urls = []
for path in visible:
    item = json.loads(path.read_text(encoding="utf-8"))
    hidden = json.loads((root / "hidden" / f"{path.stem}.json").read_text(encoding="utf-8"))
    counts[hidden["bug_class"]] += 1
    url = item["source"]["url"].rstrip("/")
    repos[url] += 1
    urls.append(item["issue"]["url"])
concurrency = counts["race"] + counts["deadlock"]
print(f"instances={len(visible)} concurrency={concurrency} lifetime={counts['lifetime']} classes={dict(counts)}")
for repo, count in repos.items():
    print(f"repo {repo} {count}")
    if count > 4:
        print(f"too many from {repo}")
        sys.exit(1)
if concurrency < 4 or counts["lifetime"] < 4:
    print("class floor missed")
    sys.exit(1)
Path("/tmp/proofsmith-trackb-urls.txt").write_text("\n".join(urls) + "\n", encoding="utf-8")
PY

fail=0
while IFS= read -r url; do
  code="$(curl -s -o /dev/null -w '%{http_code}' "$url")"
  echo "$code $url"
  if [[ "$code" != "200" ]]; then
    fail=1
  fi
done < /tmp/proofsmith-trackb-urls.txt
exit "$fail"
