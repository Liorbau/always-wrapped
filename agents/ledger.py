"""Daily cost ledger.

Per-run caps live in the harness (max_steps, max_cost_usd); this is the
cross-run layer that refuses new agent work past the daily budget.

Fails CLOSED: if the ledger cannot be read we do not know what has been spent,
and spending blind is worse than refusing.
"""

import os

from agents.store import run_costs
from core.logging import configure_logger

logger = configure_logger(__name__)

DAILY_BUDGET_USD = float(os.getenv("AGENT_DAILY_BUDGET_USD", "20.00"))

NO_BUDGET = -1.0


def daily_spent(day=None):
    """Total agent cost (USD) for a YYYYMMDD day, or None if it can't be read."""
    return run_costs.spent_on(day)


def budget_left():
    """Remaining budget for today; <= 0 means agents must refuse to run."""
    spent = run_costs.spent_on()
    if spent is None:
        logger.error("Budget ledger unreadable — refusing agent work.")
        return NO_BUDGET
    return DAILY_BUDGET_USD - spent
