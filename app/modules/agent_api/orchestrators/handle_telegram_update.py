"""Telegram webhook handling.

This is a WRITE TRIGGER: the shared secret is checked before anything acts, and
the Approve tap is additionally restricted to the owner's account. Fails closed.
"""

import hmac
import os

from agents import timers
from agents.notifications import get_notifier
from app.errors import AppError, FORBIDDEN
from app.modules.agent_api import events, planning, proposals
from core.logging import configure_logger

logger = configure_logger(__name__)

PLAN_STARTED = (
    "🗓 Planning tomorrow from your calendar — I'll send each playlist here to approve."
)
PLAN_OVER_BUDGET = "Daily agent budget reached — planning is off until tomorrow."
PLAN_BUSY = "A plan is already running — hang tight."


def execute(secret_header, update):
    _verify_secret(secret_header)
    callback = update.get("callback_query")
    if callback:
        return _handle_callback(callback)
    return _handle_message(update.get("message") or {})


def _verify_secret(provided):
    expected = os.getenv("TELEGRAM_WEBHOOK_SECRET", "")
    if not expected or not hmac.compare_digest(provided or "", expected):
        logger.warning("Telegram webhook rejected: bad secret token.")
        raise AppError(FORBIDDEN, "Forbidden.")


def _owner_chat_id():
    return os.getenv("TELEGRAM_CHAT_ID", "")


def _handle_message(message):
    chat_id = str((message.get("chat") or {}).get("id", ""))
    text = (message.get("text") or "").strip()
    owner = _owner_chat_id()
    if not text.startswith("/") or not owner or chat_id != owner:
        return {"type": "ignored"}

    if text.split()[0].split("@")[0].lower() == "/plan":
        started, reason = planning.start()
        get_notifier().send_message(chat_id, _plan_reply(started, reason))
        return {"type": "ok"}

    try:
        reply = timers.handle_command(text, chat_id)
    except Exception:
        logger.exception("Timer command failed: %s", text[:80])
        reply = "Something broke handling that — try again."
    get_notifier().send_message(chat_id, reply)
    return {"type": "ok"}


def _plan_reply(started, reason):
    if started:
        return PLAN_STARTED
    return PLAN_OVER_BUDGET if reason == "budget" else PLAN_BUSY


def _handle_callback(callback):
    owner = _owner_chat_id()
    tapper = str((callback.get("from") or {}).get("id", ""))
    if not owner or tapper != owner:
        logger.warning("Telegram callback from non-owner %s ignored.", tapper)
        get_notifier().acknowledge(callback["id"], "Not authorized.")
        return {"type": "ignored"}

    action, _, proposal_id = callback.get("data", "").partition(":")
    card = planning.CARD_REFS.pop(proposal_id, None)

    if action == "approve":
        return _approve(callback, proposal_id, card)
    if action == "reject":
        return _reject(callback, proposal_id, card)
    get_notifier().acknowledge(callback["id"], "")
    return {"type": "ok"}


def _approve(callback, proposal_id, card):
    try:
        result = proposals.push(proposal_id)
    except AppError:
        get_notifier().acknowledge(callback["id"], "Couldn't push — try again.")
        if card:
            planning.CARD_REFS[proposal_id] = card
        raise

    get_notifier().acknowledge(callback["id"], "Pushed to Spotify ✔")
    if card:
        get_notifier().update_card(
            card, f"✔ Pushed to Spotify\n{result.get('url', '')}")
    logger.info("Proposal %s approved via Telegram.", proposal_id)
    return {"type": "ok"}


def _reject(callback, proposal_id, card):
    proposals.discard(proposal_id, "rejected via Telegram")
    get_notifier().acknowledge(callback["id"], "Discarded ✘")
    if card:
        get_notifier().update_card(card, "✘ Discarded")
    events.record("user", "proposal rejected via Telegram")
    logger.info("Proposal %s rejected via Telegram.", proposal_id)
    return {"type": "ok"}
