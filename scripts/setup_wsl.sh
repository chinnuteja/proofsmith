#!/usr/bin/env bash
set -euo pipefail
ln -sfn "/mnt/c/Users/Profile 1/ByteAskEval" "$HOME/proofsmith"
mkdir -p "$HOME/psw"
python3 -m venv "$HOME/.venvs/proofsmith"
source "$HOME/.venvs/proofsmith/bin/activate"
pip install -q --upgrade pip
pip install -q -e "$HOME/proofsmith[dev]"
python -m playwright install chromium
echo "setup_wsl: OK"
