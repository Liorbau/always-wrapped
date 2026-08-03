"""Daily cost ledger.

Per-run caps live in the harness (max_steps, max_cost_usd); this is the
cross-run layer that refuses new agent work past the daily budget.

Fails CLOSED: if the ledger cannot be read we do not know what has been spent,
and spending blind is worse than refusing.
"""

import os
import time
from datetime import datetime, timedelta

from agents.store import run_costs
from core.logging import configure_logger

logger = configure_logger(__name__)

DAILY_BUDGET_USD = float(os.getenv("AGENT_DAILY_BUDGET_USD", "20.00"))

NO_BUDGET = -1.0


def _day_key(day=None):
    return day or time.strftime("%Y%m%d")


def _as_date(day):
    return datetime.strptime(day, "%Y%m%d").date()


def week_bounds(day=None):
    """Inclusive YYYYMMDD (Sun → `day`) — same Sunday week as Wrapped."""
    end = _as_date(_day_key(day))
    start = end - timedelta(days=(end.weekday() + 1) % 7)
    return start.strftime("%Y%m%d"), end.strftime("%Y%m%d")


def month_bounds(day=None):
    """Inclusive YYYYMMDD (1st of month → `day`)."""
    end = _as_date(_day_key(day))
    start = end.replace(day=1)
    return start.strftime("%Y%m%d"), end.strftime("%Y%m%d")


def daily_spent(day=None):
    """Total agent cost (USD) for a YYYYMMDD day, or None if it can't be read."""
    return run_costs.spent_on(day)


def spend_windows(day=None):
    """Today / week / month totals, or None per field when the ledger is unread.

    Week is Sunday→today. Month is the 1st→today. Same clock as `spent_on`.
    """
    day = _day_key(day)
    week_start, week_end = week_bounds(day)
    month_start, month_end = month_bounds(day)
    return {
        "today": run_costs.spent_on(day),
        "week": run_costs.spent_between(week_start, week_end),
        "month": run_costs.spent_between(month_start, month_end),
        "daily_budget": DAILY_BUDGET_USD,
    }


def format_spend_reply(windows=None):
    """Owner-facing chat line from ledger totals — arithmetic stays in code."""
    windows = windows or spend_windows()
    today, week, month = windows["today"], windows["week"], windows["month"]
    if today is None or week is None or month is None:
        return ("I can't read the spend ledger right now, so I won't guess. "
                "Check back once the database is reachable.")
    budget = windows["daily_budget"]
    return (
        f"LLM spend — today ${today:.2f} "
        f"(budget ${budget:.0f}/day) · this week ${week:.2f} "
        f"(Sun–today) · this month ${month:.2f}."
    )


def budget_left():
    """Remaining budget for today; <= 0 means agents must refuse to run."""
    spent = run_costs.spent_on()
    if spent is None:
        logger.error("Budget ledger unreadable — refusing agent work.")
        return NO_BUDGET
    return DAILY_BUDGET_USD - spent
