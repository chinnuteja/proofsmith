#!/usr/bin/env bash
set -euo pipefail
python -m proofsmith.eval.completeness
proofsmith report build
