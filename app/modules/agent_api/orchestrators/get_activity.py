from agents.ledger import spend_windows
from app.modules.agent_api import events, planning, runs


def execute():
    windows = spend_windows()
    return {
        "active": runs.active_snapshot() or _planner_activity(),
        "events": events.recent(),
        # null means the ledger could not be read — the UI shows that as unknown
        # rather than implying nothing has been spent
        "daily_cost": _money(windows["today"]),
        "week_cost": _money(windows["week"]),
        "month_cost": _money(windows["month"]),
        "daily_budget": windows["daily_budget"],
    }


def _money(value):
    return None if value is None else round(value, 4)


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
