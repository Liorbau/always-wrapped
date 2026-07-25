"""Telegram implementation of the Notifier seam.

Send-capable only; the approve/reject tap arrives at the webhook route, which
validates the secret token before anything acts. Every call is best-effort — a
Telegram hiccup must never break a Planner run.
"""

import os

import requests

from core.logging import configure_logger

logger = configure_logger(__name__)

API = "https://api.telegram.org/bot{token}/{method}"
TIMEOUT_S = 15
PREVIEW_TRACKS = 3


class TelegramNotifier:
    name = "telegram"

    def enabled(self):
        return bool(self._token())

    def send_proposal(self, block, playlist, proposal_id, recipient=None):
        chat_id = recipient or self._default_recipient()
        if not chat_id:
            logger.warning("Telegram proposal skipped: no chat id configured.")
            return None

        response = self._post("sendMessage", {
            "chat_id": chat_id,
            "text": self._proposal_text(block, playlist),
            "parse_mode": "Markdown",
            "reply_markup": self._approval_keyboard(proposal_id),
        })
        return self._card_ref(response)

    def send_message(self, recipient, text):
        return "error" not in self._post("sendMessage",
                                         {"chat_id": recipient, "text": text})

    def acknowledge(self, interaction_id, text=""):
        return "error" not in self._post(
            "answerCallbackQuery", {"callback_query_id": interaction_id, "text": text})

    def update_card(self, card_ref, text):
        if not card_ref:
            return False
        return "error" not in self._post("editMessageText", {
            "chat_id": card_ref["chat_id"], "message_id": card_ref["message_id"],
            "text": text, "parse_mode": "Markdown",
        })

    def register_webhook(self, url, secret):
        """One-time setup: point Telegram at our webhook with a secret token."""
        return self._post("setWebhook", {
            "url": url, "secret_token": secret,
            "allowed_updates": ["callback_query", "message"],
        })

    def _token(self):
        return os.getenv("TELEGRAM_BOT_TOKEN", "")

    def _default_recipient(self):
        return os.getenv("TELEGRAM_CHAT_ID", "")

    def _proposal_text(self, block, playlist):
        tracks = (playlist or {}).get("tracks") or []
        preview = ", ".join(t.get("track_name", "") for t in tracks[:PREVIEW_TRACKS])
        return (f"🎧 *{(playlist or {}).get('name', 'Playlist')}* for your "
                f"*{block['title']}* at {block['start']}\n"
                f"{len(tracks)} tracks · {preview}…\n\nPush to your Spotify?")

    def _approval_keyboard(self, proposal_id):
        return {"inline_keyboard": [[
            {"text": "✔ Approve", "callback_data": f"approve:{proposal_id}"},
            {"text": "✘ Reject", "callback_data": f"reject:{proposal_id}"},
        ]]}

    def _card_ref(self, response):
        message = (response or {}).get("result") or {}
        if not message.get("message_id"):
            return None
        return {"chat_id": message["chat"]["id"], "message_id": message["message_id"]}

    def _post(self, method, payload):
        token = self._token()
        if not token:
            return {"error": "TELEGRAM_BOT_TOKEN not set."}
        try:
            response = requests.post(API.format(token=token, method=method),
                                     json=payload, timeout=TIMEOUT_S)
            return response.json()
        except Exception as exc:
            logger.warning("Telegram %s failed: %s", method, exc)
            return {"error": f"{type(exc).__name__}: {exc}"}
