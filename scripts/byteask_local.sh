#!/usr/bin/env bash
set -euo pipefail
root="$(cd "$(dirname "$0")/.." && pwd)"
export BYTEASK_HOME="$root/.tools/byteask-home"
export BYTEASK_NO_UPDATE_CHECK=1
exec "$root/.tools/byteask/byteask" "$@"
