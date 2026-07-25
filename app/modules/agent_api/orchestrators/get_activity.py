from agents.ledger import DAILY_BUDGET_USD, daily_spent
from app.modules.agent_api import events, planning, runs


def execute():
    spent = daily_spent()
    return {
        "active": runs.active_snapshot() or _planner_activity(),
        "events": events.recent(),
        # null means the ledger could not be read — the UI shows that as unknown
        # rather than implying nothing has been spent
        "daily_cost": round(spent, 4) if spent is not None else None,
        "daily_budget": DAILY_BUDGET_USD,
    }


def _planner_activity():
    """The headless Planner isn't a chat run, so surface it separately."""
    state = planning.snapshot()
    if not state["running"]:
        return None
    return {
        "agent": "planner",
        "doing": "planning tomorrow's playlists",
        "steps": len(state["proposals"]),
        "cost": 0,
    }
