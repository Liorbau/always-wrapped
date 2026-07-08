"""Headless Planner trigger — fire the nightly 'plan tomorrow' run.

Run on a schedule the night before (cron / Render cron job):

    ./venv/bin/python scripts/plan_tomorrow.py

This POSTs to the running web app's /api/agent/plan endpoint rather than
planning in-process, because the built proposals must live in the SAME process
that later handles the Telegram Approve tap (proposals are held in memory there,
keyed for the webhook). The endpoint reads the calendar, builds playlists, and
sends Telegram proposals; the Spotify write waits for your Approve (HITL).

APP_BASE_URL points at the running app (default local dev port).
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import requests


def main():
    base = os.getenv("APP_BASE_URL", "http://127.0.0.1:5050").rstrip("/")
    try:
        r = requests.post(f"{base}/api/agent/plan", timeout=30)
        print(f"POST {base}/api/agent/plan -> {r.status_code} {r.text.strip()}")
    except Exception as exc:
        print(f"Plan trigger failed: {type(exc).__name__}: {exc}")
        sys.exit(1)


if __name__ == "__main__":
    main()
