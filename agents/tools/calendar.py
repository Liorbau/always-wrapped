"""Calendar reader: tomorrow's activity blocks from a secret .ics feed.

Read-only, no OAuth — the user supplies CALENDAR_ICS_URL (Google/Apple both
expose a private .ics link). Recurring events (daily standup, weekly gym) are
expanded via recurring_ical_events rather than hand-rolled RRULE.

Meetings are dropped; the remaining blocks (run, gym, commute, project, ...)
are what the Planner builds playlists for. Event titles are UNTRUSTED input —
returned as data, fenced as content (never instructions) downstream.
"""

import os
from datetime import datetime, timedelta, timezone

import icalendar
import recurring_ical_events
import requests

from logging_config import configure_logger

logger = configure_logger(__name__)

# Titles that mark a block as a meeting (skip — no music).
MEETING_MARKERS = ("meeting", "call", "sync", "standup", "1:1", "1-1", "interview",
                   "zoom", "meet", "webinar", "review", "catch up", "catch-up")


def _is_meeting(title):
    low = (title or "").lower()
    return any(m in low for m in MEETING_MARKERS)


def _user_tz():
    """The user's timezone (USER_TZ, default Asia/Jerusalem) so 'tomorrow' means
    their tomorrow, not UTC's — else late-night events land on the wrong day."""
    try:
        from zoneinfo import ZoneInfo
        return ZoneInfo(os.getenv("USER_TZ", "Asia/Jerusalem"))
    except Exception:  # tz database missing — degrade to UTC
        return timezone.utc


def tomorrow_blocks(ics_text=None, now=None):
    """Return tomorrow's non-meeting events as
    [{'title', 'start', 'end', 'minutes'}], sorted by start time.

    ics_text lets tests pass a fixture; production fetches CALENDAR_ICS_URL.
    now lets tests pin 'today' (defaults to real UTC now).
    """
    if ics_text is None:
        url = os.getenv("CALENDAR_ICS_URL")
        if not url:
            return {"error": "CALENDAR_ICS_URL is not set."}
        try:
            ics_text = requests.get(url, timeout=15).text
        except Exception as exc:
            logger.warning("Calendar fetch failed: %s", exc)
            return {"error": f"Calendar fetch failed: {type(exc).__name__}"}

    try:
        cal = icalendar.Calendar.from_ical(ics_text)
    except Exception as exc:
        return {"error": f"Calendar parse failed: {type(exc).__name__}"}

    tz = _user_tz()
    now = now or datetime.now(tz)
    now = now.astimezone(tz) if now.tzinfo else now.replace(tzinfo=tz)
    day = (now + timedelta(days=1)).date()
    start = datetime(day.year, day.month, day.day, tzinfo=tz)
    end = start + timedelta(days=1)

    events = recurring_ical_events.of(cal).between(start, end)
    blocks = []
    for ev in events:
        title = str(ev.get("SUMMARY", "")).strip()
        if _is_meeting(title):
            continue
        s, e = ev.get("DTSTART").dt, ev.get("DTEND").dt if ev.get("DTEND") else None
        # normalise date-only (all-day) events to naive comparison
        s_dt = s if isinstance(s, datetime) else datetime(s.year, s.month, s.day, tzinfo=tz)
        minutes = int((e - s).total_seconds() // 60) if e and isinstance(e, datetime) else None
        blocks.append({
            "title": title,
            "start": s_dt.strftime("%H:%M"),
            "minutes": minutes,
        })
    blocks.sort(key=lambda b: b["start"])
    logger.info("Calendar: %d activity block(s) tomorrow.", len(blocks))
    return {"date": day.isoformat(), "blocks": blocks}
