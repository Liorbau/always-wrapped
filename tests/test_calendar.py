"""Calendar tool tests — offline, fixture .ics (no network, no secrets).

Runnable directly:  ./venv/bin/python tests/test_calendar.py
"""

import os
import sys
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from tests import sandbox  # noqa: F401  — must precede every app import

from agents.tools.calendar import tomorrow_blocks, _is_meeting

# 'today' is pinned to 2026-07-08, so 'tomorrow' = 2026-07-09.
NOW = datetime(2026, 7, 8, 12, 0, tzinfo=timezone.utc)

ICS = """BEGIN:VCALENDAR
VERSION:2.0
PRODID:-//test//EN
BEGIN:VEVENT
UID:1
SUMMARY:Morning run
DTSTART:20260709T070000Z
DTEND:20260709T073000Z
END:VEVENT
BEGIN:VEVENT
UID:2
SUMMARY:Team standup
DTSTART:20260709T093000Z
DTEND:20260709T094500Z
END:VEVENT
BEGIN:VEVENT
UID:3
SUMMARY:Deep work: project
DTSTART:20260709T100000Z
DTEND:20260709T120000Z
END:VEVENT
BEGIN:VEVENT
UID:4
SUMMARY:Gym
DTSTART:20260710T180000Z
DTEND:20260710T190000Z
END:VEVENT
END:VCALENDAR"""


def test_meeting_filter():
    assert _is_meeting("Team standup")
    assert _is_meeting("1:1 with Dana")
    assert _is_meeting("Zoom call")
    assert not _is_meeting("Morning run")
    assert not _is_meeting("Gym")


def test_tomorrow_blocks_skips_meetings_and_other_days():
    out = tomorrow_blocks(ics_text=ICS, now=NOW)
    assert out["date"] == "2026-07-09"
    titles = [b["title"] for b in out["blocks"]]
    assert titles == ["Morning run", "Deep work: project"]  # standup dropped, gym is +2d
    run = out["blocks"][0]
    assert run["start"] == "07:00" and run["minutes"] == 30
    assert out["blocks"][1]["minutes"] == 120


def test_missing_config():
    saved = os.environ.pop("CALENDAR_ICS_URL", None)
    try:
        out = tomorrow_blocks()
        assert "error" in out
    finally:
        if saved is not None:
            os.environ["CALENDAR_ICS_URL"] = saved


if __name__ == "__main__":
    test_meeting_filter()
    test_tomorrow_blocks_skips_meetings_and_other_days()
    test_missing_config()
    print("OK: all calendar tests passed")
