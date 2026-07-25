"""GET /api/records — personal listening highs from listening_history.

Runnable directly:  ./venv/bin/python tests/test_records.py
"""

import os
import sqlite3
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from tests import sandbox  # noqa: F401  — must precede every app import

import app.modules.music.repository as music_repo
from app.modules.music.orchestrators import get_records
from db.sqlite_time import register_time_udfs

_ROW = (
    "played_at TEXT PRIMARY KEY, track_id TEXT, track_name TEXT, artist_name TEXT, "
    "album_name TEXT, album_image_url TEXT, artist_id TEXT, artist_image_url TEXT, "
    "duration_ms INTEGER, artist_genres TEXT"
)


def _play(played_at, track_id="t"):
    return (played_at, track_id, "Song", "Artist", "Al", None, "a1", None, 200000, "pop")


def _with_db(rows, fn):
    with tempfile.TemporaryDirectory() as tmp:
        path = os.path.join(tmp, "records.db")
        conn = sqlite3.connect(path)
        register_time_udfs(conn)
        conn.execute(f"CREATE TABLE listening_history ({_ROW})")
        for row in rows:
            conn.execute(
                "INSERT INTO listening_history VALUES (?,?,?,?,?,?,?,?,?,?)", row)
        conn.commit()
        conn.close()

        def connect(readonly=False):
            c = sqlite3.connect(path)
            register_time_udfs(c)
            return c, "sqlite"

        original = music_repo.get_db_connection
        music_repo.get_db_connection = connect
        try:
            return fn()
        finally:
            music_repo.get_db_connection = original


def test_empty_history_returns_no_records():
    payload = _with_db([], lambda: get_records.execute(tz="UTC"))
    assert payload == {"records": []}


def test_records_pick_peak_week_month_and_day():
    rows = [
        _play("2026-07-06T12:00:00Z", "w1"),
        _play("2026-07-07T12:00:00Z", "w2"),
        _play("2026-07-13T12:00:00Z", "w3"),
        _play("2026-07-14T12:00:00Z", "w4"),
        _play("2026-07-14T18:00:00Z", "w5"),
        _play("2026-07-15T12:00:00Z", "d1"),
        _play("2026-07-15T18:00:00Z", "d2"),
        _play("2026-07-15T21:00:00Z", "d3"),
        _play("2026-06-01T12:00:00Z", "m1"),
    ]
    payload = _with_db(rows, lambda: get_records.execute(tz="UTC"))
    by_kind = {r["kind"]: r for r in payload["records"]}

    week = by_kind["most_active_week"]
    assert week["window_start"] == "2026-07-12"
    assert week["window_end"] == "2026-07-18"
    assert week["value"] == 6

    month = by_kind["most_active_month"]
    assert month["window_start"] == "2026-07-01"
    assert month["window_end"] == "2026-07-31"
    assert month["value"] == 8

    day = by_kind["busiest_day"]
    assert day["window_start"] == day["window_end"] == "2026-07-15"
    assert day["value"] == 3


def test_records_honor_local_timezone_for_day_boundaries():
    rows = [
        _play("2026-07-06T21:00:00Z", "late"),
        _play("2026-07-06T22:00:00Z", "late2"),
    ]
    payload = _with_db(rows, lambda: get_records.execute(tz="Asia/Jerusalem"))
    day = next(r for r in payload["records"] if r["kind"] == "busiest_day")
    assert day["window_start"] == "2026-07-07"
    assert day["value"] == 2


if __name__ == "__main__":
    test_empty_history_returns_no_records()
    test_records_pick_peak_week_month_and_day()
    test_records_honor_local_timezone_for_day_boundaries()
    print("OK: all records tests passed")
