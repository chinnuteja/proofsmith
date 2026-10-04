#!/usr/bin/env bash
set -euo pipefail
# Same flags as proofsmith byteask-patch. Requires a previously sealed supplied check.
exec proofsmith byteask-patch "$@"
