#!/usr/bin/env bash
set -euo pipefail
echo "== tracka"
if [[ -d "${HOME}/psw/tracka" ]]; then
  find "${HOME}/psw/tracka" -mindepth 1 -maxdepth 1 -type d -printf '%f\n' | sort
else
  echo none
fi
echo "== ok caches"
find "${HOME}/psw/cache/builds" -name .proofsmith-ok 2>/dev/null | wc -l
echo "== newest logs"
find "${HOME}/psw/cache/builds" -name build.log -printf '%T@ %p\n' 2>/dev/null | sort -n | tail -6
newest="$(find "${HOME}/psw/cache/builds" -name build.log -printf '%T@ %p\n' 2>/dev/null | sort -n | tail -1 | cut -d' ' -f2-)"
if [[ -n "${newest}" ]]; then
  echo "== tail ${newest}"
  tail -n 15 "${newest}"
fi
echo "== pytest"
ps -ef | grep -E 'pytest|test_tracka' | grep -v grep || true
