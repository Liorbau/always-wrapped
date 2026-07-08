"""Telegram notifier for the Planner: send a playlist proposal with inline
Approve / Reject buttons, and helpers to answer callbacks + register the
webhook.

Send-capable only; the approval callback is handled by the webhook route in
agents/api.py, which validates the secret token before acting. All calls are
best-effort — a Telegram hiccup never breaks the Planner run.
"""

import os

import requests

from logging_config import configure_logger

logger = configure_logger(__name__)

API = "https://api.telegram.org/bot{token}/{method}"


def _token():
    return os.getenv("TELEGRAM_BOT_TOKEN", "")


def _post(method, payload):
    token = _token()
    if not token:
        return {"error": "TELEGRAM_BOT_TOKEN not set."}
    try:
        r = requests.post(API.format(token=token, method=method), json=payload, timeout=15)
        return r.json()
    except Exception as exc:
        logger.warning("Telegram %s failed: %s", method, exc)
        return {"error": f"{type(exc).__name__}: {exc}"}


def send_proposal(block, playlist, proposal_id, chat_id=None):
    """Notify the user about a built playlist with Approve/Reject buttons."""
    chat_id = chat_id or os.getenv("TELEGRAM_CHAT_ID")
    if not chat_id:
        return {"error": "TELEGRAM_CHAT_ID not set."}
    tracks = (playlist or {}).get("tracks") or []
    preview = ", ".join(t.get("track_name", "") for t in tracks[:3])
    text = (f"🎧 *{playlist.get('name', 'Playlist')}* for your "
            f"*{block['title']}* at {block['start']}\n"
            f"{len(tracks)} tracks · {preview}…\n\nPush to your Spotify?")
    keyboard = {"inline_keyboard": [[
        {"text": "✔ Approve", "callback_data": f"approve:{proposal_id}"},
        {"text": "✘ Reject", "callback_data": f"reject:{proposal_id}"},
    ]]}
    return _post("sendMessage", {"chat_id": chat_id, "text": text,
                                 "parse_mode": "Markdown", "reply_markup": keyboard})


def send_message(chat_id, text):
    """Plain text message (timer replies, failure notices)."""
    return _post("sendMessage", {"chat_id": chat_id, "text": text})


def answer_callback(callback_id, text=""):
    return _post("answerCallbackQuery", {"callback_query_id": callback_id, "text": text})


def edit_message(chat_id, message_id, text):
    return _post("editMessageText", {"chat_id": chat_id, "message_id": message_id,
                                     "text": text, "parse_mode": "Markdown"})


def set_webhook(url, secret):
    """One-time: point Telegram at our webhook with a secret header token."""
    return _post("setWebhook", {"url": url, "secret_token": secret,
                                "allowed_updates": ["callback_query", "message"]})
