"""Standing playlist timers: the scheduler thread and what a firing does.

Read-only on the account — a fired timer proposes over Telegram and waits.
"""

import os
import threading

from agents import timers
from agents.dj import build_dj, run_dj_turn
from agents.ledger import budget_left
from agents.notifications import get_notifier
from app.modules.agent_api import events, planning, proposals
from core.logging import configure_logger

logger = configure_logger(__name__)

DEFAULT_PLANNER_TIME = "21:00"


def fire(row):
    notifier = get_notifier()
    events.record("timer", f"⏰ #{row['id']} fired: {row['prompt'][:60]}")
    if budget_left() <= 0:
        notifier.send_message(
            row["chat_id"],
            f"⏰ Timer #{row['id']} skipped — daily agent budget reached.",
        )
        return

    try:
        outcome = run_dj_turn(build_dj(), row["prompt"])
    except Exception:
        logger.exception("Timer %s DJ run failed.", row["id"])
        notifier.send_message(
            row["chat_id"],
            f"⏰ Timer #{row['id']} failed — couldn't build the playlist this time.",
        )
        return

    playlist = outcome.get("playlist")
    if not playlist:
        notifier.send_message(
            row["chat_id"],
            f"⏰ Timer #{row['id']}: no playlist this time. "
            f"{(outcome.get('response') or '')[:200]}",
        )
        return

    proposal_id = proposals.register(playlist)
    block = {"title": f"timer #{row['id']}", "start": row["at_hhmm"]}
    planning.remember_card(
        proposal_id,
        notifier.send_proposal(block, playlist, proposal_id, recipient=row["chat_id"]),
    )
    events.record("timer", f"proposed '{playlist.get('name', '?')}' awaiting approval")


def start_thread():
    """Once-a-minute scheduler: standing timers plus the nightly Planner."""
    daily = (os.getenv("PLANNER_TIME", DEFAULT_PLANNER_TIME), planning.start)
    threading.Thread(
        target=timers.start_timer_service,
        args=(fire,),
        kwargs={"daily": daily},
        daemon=True,
    ).start()
