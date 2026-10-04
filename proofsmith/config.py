"""Constants from the Proofsmith global constraints."""

from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

REPO = Path(__file__).resolve().parents[1]
WORK = Path(os.environ.get("PROOFSMITH_WORK_DIR", str(Path.home() / "psw"))).expanduser().resolve()
SITE = REPO / "site"
RESULTS = Path(os.environ.get("PROOFSMITH_RESULTS_DIR", str(REPO / "results"))).expanduser().resolve()
RUNS = REPO / "runs"

load_dotenv(REPO / ".env")

RUNTIME_N = 10
RUNTIME_K = 8
EVAL_N = 20
EVAL_BUGGY_K = 16
EVAL_FIXED_MAX_FAILS = 0
RUN_TIMEOUT_S = 60
SIGNATURE_FRAMES = 3

MAX_STEPS = 50
MAX_TOTAL_TOKENS = 500000
MAX_WALL_S = 1800

EVAL_MODEL = "deepseek-v4-pro"
DEV_MODEL = "deepseek-flash"
API_BASE = "https://api.deepseek.com"
MAX_USD = float(os.environ.get("PROOFSMITH_MAX_USD", "4.50"))
