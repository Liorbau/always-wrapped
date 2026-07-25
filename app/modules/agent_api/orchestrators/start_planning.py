from app.errors import budget_exhausted, conflict
from app.modules.agent_api import planning


def execute():
    started, reason = planning.start()
    if started:
        return {"type": "planning"}
    if reason == "budget":
        raise budget_exhausted("Daily budget reached.")
    raise conflict("A plan is already running.")
