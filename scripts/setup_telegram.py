"""One-time: register the Telegram webhook so Approve/Reject taps reach the app.

Run once after the app is deployed (and again if the public URL changes):

    APP_BASE_URL=https://always-wrapped.onrender.com \\
        ./venv/bin/python scripts/setup_telegram.py

Points Telegram at <APP_BASE_URL>/api/agent/telegram/webhook with the secret
token from TELEGRAM_WEBHOOK_SECRET — Telegram echoes that header on every
callback, and the webhook rejects anything that doesn't match (the write-path
guard). Needs TELEGRAM_BOT_TOKEN + TELEGRAM_WEBHOOK_SECRET in the environment.
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv

from agents import telegram

load_dotenv()


def main():
    base = os.getenv("APP_BASE_URL")
    secret = os.getenv("TELEGRAM_WEBHOOK_SECRET")
    if not base or not secret:
        print("Set APP_BASE_URL and TELEGRAM_WEBHOOK_SECRET (+ TELEGRAM_BOT_TOKEN) first.")
        sys.exit(1)
    url = f"{base.rstrip('/')}/api/agent/telegram/webhook"
    resp = telegram.set_webhook(url, secret)
    print(f"setWebhook -> {resp}")
    if not resp.get("ok"):
        sys.exit(1)
    print(f"Webhook registered at {url}")


if __name__ == "__main__":
    main()
