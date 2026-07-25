"""Headless Planner runs: tomorrow's calendar becomes per-block proposals.

Read-only on the Spotify account. Every proposal still waits for an Approve,
whether the human taps it in the app or in Telegram.
"""

import threading

from agents.ledger import budget_left
from agents.notifications import get_notifier
from agents.planner import plan_tomorrow
from app.modules.agent_api import events, proposals
from core.logging import configure_logger

logger = configure_logger(__name__)

# proposal_id -> opaque notifier card reference, so an Approve can update the
# card it was tapped on. Only the notifier knows what is inside.
CARD_REFS = {}

_busy = {"on": False}
_state = {"running": False, "date": None, "proposals": [], "error": None}


def snapshot():
    return dict(_state)


def start():
    """Single entry point for every trigger (chat, /plan, endpoint, nightly).
    Returns (started, reason)."""
    if budget_left() <= 0:
        return False, "budget"
    if _busy["on"]:
        return False, "busy"
    _busy["on"] = True
    threading.Thread(target=_run, daemon=True).start()
    return True, ""


def remember_card(proposal_id, card_ref):
    if card_ref:
        CARD_REFS[proposal_id] = card_ref


def _run():
    _state.update(running=True, date=None, proposals=[], error=None)
    try:
        events.record("planner", "reading tomorrow's calendar")
        outcome = plan_tomorrow()
        if "error" in outcome:
            events.record("planner", f"stopped: {outcome['error']}")
            _state["error"] = outcome["error"]
            return

        _state["date"] = outcome.get("date")
        planned = outcome.get("proposals", [])
        for plan in planned:
            _publish(plan)
        events.record("planner", f"done: {len(planned)} playlist(s) awaiting approval")
        logger.info(
            "Planner run: %d proposal(s), $%.4f.", len(planned), outcome.get("cost_usd", 0)
        )
    except Exception as exc:
        logger.exception("Planner run failed.")
        events.record("planner", f"failed: {type(exc).__name__}")
        _state["error"] = "Planner error — check server logs."
    finally:
        _state["running"] = False
        _busy["on"] = False


def _publish(plan):
    proposal_id = proposals.register(plan["playlist"])
    block = plan["block"]
    _state["proposals"].append({
        "proposal_id": proposal_id,
        "block": block,
        "playlist": plan["playlist"],
        "response": plan.get("response", ""),
    })
    events.record(
        "planner", f"proposed '{plan['playlist'].get('name', '?')}' for {block['title']}"
    )
    remember_card(proposal_id,
                  get_notifier().send_proposal(block, plan["playlist"], proposal_id))
