#!/usr/bin/env bash
set -euo pipefail
cd ~/proofsmith
mkdir -p runs site
if [[ -f runs/serve.pid ]]; then
  old="$(cat runs/serve.pid || true)"
  if [[ -n "${old}" ]]; then
    kill "${old}" 2>/dev/null || true
  fi
fi
if command -v fuser >/dev/null 2>&1; then
  fuser -k 8765/tcp >/dev/null 2>&1 || true
fi
sleep 0.2
# shellcheck disable=SC1090
source ~/.venvs/proofsmith/bin/activate
: > runs/serve.log
nohup python -m http.server 8765 --directory site >> runs/serve.log 2>&1 &
echo $! > runs/serve.pid
disown || true
ok=0
for _ in $(seq 1 50); do
  code="$(curl -s -o /dev/null -w "%{http_code}" http://127.0.0.1:8765/ || true)"
  if [[ "${code}" == "200" ]]; then
    ok=1
    break
  fi
  sleep 0.2
done
if [[ "${ok}" != "1" ]]; then
  echo "serve: FAIL" >&2
  cat runs/serve.log >&2 || true
  exit 1
fi
echo "serve: OK"
