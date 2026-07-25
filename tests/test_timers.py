"""Tests for the standing playlist timers (agents/timers.py).

Pure logic (day parsing, due window) plus a command roundtrip against a
temp SQLite db — no network, no LLM.
"""

import datetime
import os
import sqlite3
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from tests import sandbox  # noqa: F401  — must precede every app import

from agents import timers
from db import settings as db_settings


def _patch_db(path):
    def _connect(readonly=False):
        conn = sqlite3.connect(path)
        return conn, "sqlite"
    timers.get_db_connection = _connect
    db_settings.get_db_connection = _connect


def test_expand_days():
    assert timers.expand_days("daily") == list(timers.DAYS)
    assert timers.expand_days("mon-wed") == ["mon", "tue", "wed"]
    assert timers.expand_days("sun-thu") == ["sun", "mon", "tue", "wed", "thu"]
    assert timers.expand_days("mon,wed,fri") == ["mon", "wed", "fri"]
    assert timers.expand_days("noday") is None
    assert timers.expand_days("mon-noday") is None


def test_parse_timer():
    out = timers.parse_timer("/timer 7:30 sun-thu a 50-min upbeat train playlist")
    assert out == {"at": "07:30", "days": ["sun", "mon", "tue", "wed", "thu"],
                   "prompt": "a 50-min upbeat train playlist"}
    assert "error" in timers.parse_timer("/timer 25:99 daily x")
    assert "error" in timers.parse_timer("/timer 07:30 nday x")
    assert "error" in timers.parse_timer("/timer")


def test_due_window():
    with tempfile.NamedTemporaryFile(suffix=".db") as tmp:
        _patch_db(tmp.name)
        tid = timers.add_timer("07:30", ["wed"], "train playlist", "42")
        wed = datetime.datetime(2026, 7, 8, 7, 45)  # a Wednesday, 15 min late
        assert [t["id"] for t in timers.due_timers(now=wed)] == [tid]
        # wrong day, too early, and past the grace window: not due
        assert timers.due_timers(now=datetime.datetime(2026, 7, 9, 7, 45)) == []
        assert timers.due_timers(now=datetime.datetime(2026, 7, 8, 7, 29)) == []
        assert timers.due_timers(now=datetime.datetime(2026, 7, 8, 8, 31)) == []
        # already fired today: not due again
        timers.mark_fired(tid, "2026-07-08")
        assert timers.due_timers(now=wed) == []


def test_daily_due():
    d = datetime.datetime(2026, 7, 8, 21, 5)  # 5 min after 21:00
    assert timers.daily_due("21:00", d, last_date=None)          # in window, not fired
    assert not timers.daily_due("21:00", d, last_date="2026-07-08")  # already fired today
    assert not timers.daily_due("21:00", datetime.datetime(2026, 7, 8, 20, 59), None)  # too early
    assert not timers.daily_due("21:00", datetime.datetime(2026, 7, 8, 22, 1), None)   # past grace


def test_parse_plantime():
    assert timers.parse_plantime("/plantime 7:30") == {"at": "07:30"}
    assert timers.parse_plantime("/plantime OFF") == {"at": None}
    assert timers.parse_plantime("/plantime") == {}       # no argument: just report
    assert "error" in timers.parse_plantime("/plantime 25:99")
    assert "error" in timers.parse_plantime("/plantime whenever")


def test_planner_time_is_off_until_the_owner_picks_one():
    with tempfile.NamedTemporaryFile(suffix=".db") as tmp:
        _patch_db(tmp.name)
        assert timers.planner_time() is None
        timers.set_planner_time("21:00")
        assert timers.planner_time() == "21:00"
        timers.set_planner_time("07:15")                  # overwrites, not appends
        assert timers.planner_time() == "07:15"
        timers.set_planner_time(None)
        assert timers.planner_time() is None


def test_daily_hhmm_rereads_a_callable_every_tick():
    assert timers.daily_hhmm(("21:00", None)) == "21:00"
    schedule = ["21:00"]
    daily = (lambda: schedule[0], None)
    assert timers.daily_hhmm(daily) == "21:00"
    schedule[0] = None                                    # switched off mid-run
    assert timers.daily_hhmm(daily) is None


def test_plantime_command_roundtrip():
    with tempfile.NamedTemporaryFile(suffix=".db") as tmp:
        _patch_db(tmp.name)
        assert "is off" in timers.handle_command("/plantime", "42")
        assert "21:00" in timers.handle_command("/plantime 21:00", "42")
        assert "21:00" in timers.handle_command("/plantime", "42")
        assert "use HH:MM" in timers.handle_command("/plantime nope", "42")
        assert timers.planner_time() == "21:00"           # a bad edit changes nothing
        assert "off" in timers.handle_command("/plantime off", "42")
        assert timers.planner_time() is None


def test_command_roundtrip():
    with tempfile.NamedTemporaryFile(suffix=".db") as tmp:
        _patch_db(tmp.name)
        reply = timers.handle_command(
            "/timer 07:30 sun-thu a 50-min upbeat train playlist", "42")
        assert "#1" in reply and "07:30" in reply
        listing = timers.handle_command("/timers", "42")
        assert "train playlist" in listing
        assert "removed" in timers.handle_command("/deltimer 1", "42")
        assert "No timers set" in timers.handle_command("/timers", "42")
        assert "No timer" in timers.handle_command("/deltimer 9", "42")
        assert "Usage" in timers.handle_command("/help", "42")


if __name__ == "__main__":
    test_daily_due()
    test_expand_days()
    test_parse_timer()
    test_parse_plantime()
    test_planner_time_is_off_until_the_owner_picks_one()
    test_daily_hhmm_rereads_a_callable_every_tick()
    test_plantime_command_roundtrip()
    test_due_window()
    test_command_roundtrip()
    print("test_timers: all passed")
