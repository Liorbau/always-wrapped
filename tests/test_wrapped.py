"""Wrapped pipeline tests — temp DB, FakeLLM, no network.

Runnable directly:  ./venv/bin/python tests/test_wrapped.py
"""

import json
import os
import sqlite3
import sys
import tempfile
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import agents.evaluator as ev
import pipelines.wrapped as wr
from tests.test_harness import FakeLLM


def _make_db(path, n=25):
    conn = sqlite3.connect(path)
    conn.execute("""CREATE TABLE listening_history (
        played_at TEXT PRIMARY KEY, track_id TEXT, track_name TEXT,
        artist_name TEXT, album_name TEXT, album_image_url TEXT, artist_id TEXT,
        artist_image_url TEXT, duration_ms INTEGER, artist_genres TEXT,
        album_release_date TEXT)""")
    now = time.time()
    for i in range(n):
        ts = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(now - i * 600))
        conn.execute("INSERT INTO listening_history VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                     (ts, f"t{i % 6}", f"Song {i % 6}", f"Artist {i % 3}", "Al", None,
                      f"a{i % 3}", None, 200000, "pop", "199" if i % 2 else "2023-01-01"))
    conn.commit()
    conn.close()


def _patched(path):
    def _connect(readonly=False):
        return sqlite3.connect(path), "sqlite"
    return _connect


GOOD_STYLE = {"satisfied": True, "emoji": "🌊",
              "cards": {"title": ["Big Week", "seven days of sound"]}}


def test_pipeline_generates_and_caches():
    with tempfile.TemporaryDirectory() as tmp:
        db = os.path.join(tmp, "w.db")
        _make_db(db)
        originals = (wr.get_db_connection, ev.top_biases, wr._log_cost)
        wr.get_db_connection = _patched(db)
        ev.top_biases = lambda limit=3: [{"kind": "artist", "key": "X", "weight": 0.5}]
        costs = []
        wr._log_cost = lambda c: costs.append(c)
        try:
            llm = FakeLLM([{"content": json.dumps(GOOD_STYLE)}])
            ed = wr.get_wrapped("week", llm=llm)
            assert ed["theme"]["emoji"] == "🌊"
            assert ed["copy"]["title"] == ["Big Week", "seven days of sound"]
            assert ed["stats"]["plays"] == 25
            assert ed["stats"]["top_artists"][0]["plays"] == 9
            assert ed["stats"]["dj"]["learned"][0]["key"] == "X"
            assert len(costs) == 1

            # second call: served from cache, no LLM involved
            ed2 = wr.get_wrapped("week", llm=None)
            assert ed2["generated_at"] == ed["generated_at"]

            # force: regenerates (new LLM call)
            llm2 = FakeLLM([{"content": json.dumps(dict(GOOD_STYLE, emoji="🔥"))}])
            ed3 = wr.get_wrapped("week", force=True, llm=llm2)
            assert ed3["theme"]["emoji"] == "🔥"
        finally:
            wr.get_db_connection, ev.top_biases, wr._log_cost = originals


def test_invalid_style_falls_back_visibly():
    with tempfile.TemporaryDirectory() as tmp:
        db = os.path.join(tmp, "w.db")
        _make_db(db)
        originals = (wr.get_db_connection, ev.top_biases, wr._log_cost)
        wr.get_db_connection = _patched(db)
        ev.top_biases = lambda limit=3: []
        wr._log_cost = lambda c: None
        try:
            bad = {"satisfied": True, "emoji": "way-too-long-not-an-emoji-string"}
            ed = wr.get_wrapped("week", llm=FakeLLM([{"content": json.dumps(bad)}]))
            assert ed["theme"]["emoji"] == wr.FALLBACK_THEME["emoji"]
        finally:
            wr.get_db_connection, ev.top_biases, wr._log_cost = originals


def test_empty_period():
    with tempfile.TemporaryDirectory() as tmp:
        db = os.path.join(tmp, "w.db")
        _make_db(db, n=3)  # under MIN_PLAYS
        originals = (wr.get_db_connection, ev.top_biases)
        wr.get_db_connection = _patched(db)
        ev.top_biases = lambda limit=3: []
        try:
            ed = wr.get_wrapped("week", llm=FakeLLM([{"content": "unused"}]))
            assert ed["empty"] is True
        finally:
            wr.get_db_connection, ev.top_biases = originals


def test_period_bounds():
    from datetime import datetime, timedelta, timezone
    # week starts on SUNDAY
    start, end_ex, prev, key, label = wr._period_bounds("week")
    start_d = datetime.strptime(start[:10], "%Y-%m-%d").date()
    assert start_d.weekday() == 6, "week must start on Sunday"
    today = datetime.now(timezone.utc).date()
    assert (today - start_d).days <= 6
    assert key == f"week-{start_d.isoformat()}"

    # custom: inclusive end, prev window of equal length
    start, end_ex, prev, key, label = wr._period_bounds("custom", "2026-06-01", "2026-06-10")
    assert start == "2026-06-01T00:00:00Z"
    assert end_ex == "2026-06-11T00:00:00Z"      # inclusive end -> exclusive +1d
    assert prev == "2026-05-22T00:00:00Z"        # same 10-day length before
    assert key == "custom-2026-06-01-2026-06-10"

    # all time: everything counts, stable cache key
    start, end_ex, prev, key, label = wr._period_bounds("all")
    assert start == "2000-01-01T00:00:00Z" and key == "alltime"

    try:
        wr._period_bounds("custom", "2026-06-10", "2026-06-01")
        raise AssertionError("end<start accepted")
    except ValueError:
        pass


def test_custom_range_filters_inclusively():
    with tempfile.TemporaryDirectory() as tmp:
        db = os.path.join(tmp, "w.db")
        conn = sqlite3.connect(db)
        conn.execute("""CREATE TABLE listening_history (
            played_at TEXT PRIMARY KEY, track_id TEXT, track_name TEXT,
            artist_name TEXT, album_name TEXT, album_image_url TEXT, artist_id TEXT,
            artist_image_url TEXT, duration_ms INTEGER, artist_genres TEXT,
            album_release_date TEXT)""")
        for day, n in (("2026-05-31", 5), ("2026-06-01", 11), ("2026-06-10", 12), ("2026-06-11", 7)):
            for i in range(n):
                conn.execute("INSERT INTO listening_history VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                             (f"{day}T10:00:{i:02d}Z", f"t{i}", f"S{i}", "A", "Al",
                              None, "a1", None, 200000, "pop", "2000"))
        conn.commit(); conn.close()

        originals = (wr.get_db_connection, ev.top_biases)
        wr.get_db_connection = _patched(db)
        ev.top_biases = lambda limit=3: []
        try:
            s = wr.collect_stats("custom", start="2026-06-01", end="2026-06-10")
            assert s["plays"] == 23           # both boundary days included
            assert s["prev_plays"] == 5       # the 10 days before: only May 31
            assert s["label"].startswith("Jun 01")
        finally:
            wr.get_db_connection, ev.top_biases = originals



if __name__ == "__main__":
    test_pipeline_generates_and_caches()
    test_invalid_style_falls_back_visibly()
    test_empty_period()
    test_period_bounds()
    test_custom_range_filters_inclusively()
    print("OK: all wrapped tests passed")
