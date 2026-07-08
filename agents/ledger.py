"""Daily cost ledger over agent run logs.

Per-run caps live in the harness (max_steps, max_cost_usd); this is the
cross-run layer: sum today's spend from agent-runs/*.json and refuse new agent
work past the daily budget. Fail-closed at the chat endpoint.
"""

import glob
import json
import os
import time

from logging_config import configure_logger

logger = configure_logger(__name__)

DAILY_BUDGET_USD = float(os.getenv("AGENT_DAILY_BUDGET_USD", "20.00"))


def daily_spent(run_dir="agent-runs", day=None):
    """Total agent cost (USD) recorded in run logs for the given YYYYMMDD day."""
    day = day or time.strftime("%Y%m%d")
    total = 0.0
    for path in glob.glob(os.path.join(run_dir, f"run-{day}-*.json")):
        try:
            with open(path) as f:
                total += json.load(f)["metadata"].get("cost_usd", 0.0)
        except Exception:  # a corrupt log must not break budgeting
            logger.warning("Unreadable run log skipped: %s", path)
    return total


def budget_left(run_dir="agent-runs"):
    """Remaining budget for today; <= 0 means agents must refuse to run."""
    return DAILY_BUDGET_USD - daily_spent(run_dir=run_dir)
