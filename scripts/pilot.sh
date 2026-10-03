#!/usr/bin/env bash
set -euo pipefail
cd "${HOME}/proofsmith"
source "${HOME}/.venvs/proofsmith/bin/activate"
proofsmith protocol validate
proofsmith evaluate --pilot
proofsmith report readme
proofsmith report build
