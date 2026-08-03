"""Deterministic LLM spend answers for chat — no model arithmetic."""

from agents.ledger import format_spend_reply, spend_windows


def chat_reply():
    windows = spend_windows()
    return {
        "type": "spend",
        "response": format_spend_reply(windows),
        "today": _money(windows["today"]),
        "week": _money(windows["week"]),
        "month": _money(windows["month"]),
        "daily_budget": windows["daily_budget"],
    }


def _money(value):
    return None if value is None else round(value, 4)
