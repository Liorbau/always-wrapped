"""Wrapped pipeline tests — temp DB, FakeLLM, no network.

Runnable directly:  ./venv/bin/python tests/test_wrapped.py
"""

import contextlib
import json
import os
import sqlite3
import sys
import tempfile
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from tests import sandbox  # noqa: F401  — must precede every app import

import agents.evaluator as ev
import pipelines.wrapped as wr
from agents.ledger import DAILY_BUDGET_USD
from agents.store import hitl, run_costs
from tests.test_harness import FakeLLM
from db.sqlite_time import register_time_udfs


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


def _add_plays(path, n, track, artist):
    """More listening after an edition was cached, offset off _make_db's grid."""
    conn = sqlite3.connect(path)
    now = time.time()
    for i in range(n):
        ts = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(now - i * 600 - 37))
        conn.execute("INSERT INTO listening_history VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                     (ts, "new", track, artist, "Al", None, "anew", None, 200000,
                      "pop", "2023-01-01"))
    conn.commit()
    conn.close()


def _patched(path):
    def _connect(readonly=False):
        conn = sqlite3.connect(path)
        register_time_udfs(conn)
        return conn, "sqlite"
    return _connect


@contextlib.contextmanager
def wrapped_db(path, biases=()):
    """Point the pipeline and the agent stores at one SQLite file, as in prod.

    The stores matter here because the pipeline consults the spend ledger, which
    now fails closed when it cannot be read.
    """
    modules = (wr, run_costs, hitl)
    originals = [(module, module.get_db_connection) for module in modules]
    original_biases = ev.top_biases
    for module in modules:
        module.get_db_connection = _patched(path)
    ev.top_biases = lambda limit=3: list(biases)
    try:
        yield
    finally:
        for module, connect in originals:
            module.get_db_connection = connect
        ev.top_biases = original_biases


GOOD_STYLE = {"satisfied": True, "emoji": "🌊",
              "cards": {"title": ["Big Week", "seven days of sound"]}}

# copy that quotes the stats it was written from, the way the real model does
QUOTING_STYLE = {"satisfied": True, "emoji": "🌊", "cards": {
    "title": ["Big Week", "seven days of sound"],
    "top_songs": ["Your top 5 anthems:"],
    "volume": ["25 plays spun!", "162 less than last week!"],
    "top_song": ["'Song 0' sparkled the most!"],
}}


def test_pipeline_generates_and_caches():
    with tempfile.TemporaryDirectory() as tmp:
        db = os.path.join(tmp, "w.db")
        _make_db(db)
        biases = [{"kind": "artist", "key": "X", "weight": 0.5}]
        with wrapped_db(db, biases=biases):
            llm = FakeLLM([{"content": json.dumps(GOOD_STYLE)}])
            ed = wr.get_wrapped("week", llm=llm)
            assert ed["theme"]["emoji"] == "🌊"
            assert ed["copy"]["title"] == ["Big Week", "seven days of sound"]
            assert ed["stats"]["plays"] == 25
            assert ed["stats"]["top_artists"][0]["plays"] == 9
            assert ed["stats"]["dj"]["learned"][0]["key"] == "X"
            # generation cost landed in the ledger, so it counts against the cap
            assert run_costs.spent_on() > 0

            # second call: served from cache, no LLM involved
            ed2 = wr.get_wrapped("week", llm=None)
            assert ed2["generated_at"] == ed["generated_at"]

            # force: regenerates (new LLM call)
            llm2 = FakeLLM([{"content": json.dumps(dict(GOOD_STYLE, emoji="🔥"))}])
            ed3 = wr.get_wrapped("week", force=True, llm=llm2)
            assert ed3["theme"]["emoji"] == "🔥"


def test_reopening_shows_fresh_stats_and_drops_outdated_copy():
    with tempfile.TemporaryDirectory() as tmp:
        db = os.path.join(tmp, "w.db")
        _make_db(db)
        with wrapped_db(db):
            llm = FakeLLM([{"content": json.dumps(QUOTING_STYLE)}])
            first = wr.get_wrapped("week", llm=llm)
            assert first["stats"]["plays"] == 25

            _add_plays(db, 9, track="Newcomer", artist="Newcomer Band")

            again = wr.get_wrapped("week", llm=None)
            assert again["stats"]["plays"] == 34               # live, not the snapshot
            assert again["stats"]["top_songs"][0]["track"] == "Newcomer"
            assert again["generated_at"] == first["generated_at"]   # no regeneration
            assert again["copy"]["title"] == QUOTING_STYLE["cards"]["title"]
            assert again["copy"]["top_songs"]                  # list header still true
            assert "volume" not in again["copy"]               # quoted the old 25
            assert "top_song" not in again["copy"]             # named the old leader


def test_reopening_keeps_copy_when_nothing_moved():
    with tempfile.TemporaryDirectory() as tmp:
        db = os.path.join(tmp, "w.db")
        _make_db(db)
        with wrapped_db(db):
            llm = FakeLLM([{"content": json.dumps(QUOTING_STYLE)}])
            first = wr.get_wrapped("week", llm=llm)
            again = wr.get_wrapped("week", llm=None)
            assert again["copy"] == first["copy"]


def test_generation_stops_when_the_budget_is_gone():
    """The cap now lives in the DB, so a big recorded spend must block generation."""
    with tempfile.TemporaryDirectory() as tmp:
        db = os.path.join(tmp, "w.db")
        _make_db(db)
        with wrapped_db(db):
            run_costs.record("earlier-run", DAILY_BUDGET_USD + 1.0)
            ed = wr.get_wrapped("week", llm=FakeLLM([{"content": "unused"}]))
            assert ed["empty"] is True and "budget" in ed["message"].lower()


def test_invalid_style_falls_back_visibly():
    with tempfile.TemporaryDirectory() as tmp:
        db = os.path.join(tmp, "w.db")
        _make_db(db)
        with wrapped_db(db):
            bad = {"satisfied": True, "emoji": "way-too-long-not-an-emoji-string"}
            ed = wr.get_wrapped("week", llm=FakeLLM([{"content": json.dumps(bad)}]))
            assert ed["theme"]["emoji"] == wr.FALLBACK_THEME["emoji"]


def test_empty_period():
    with tempfile.TemporaryDirectory() as tmp:
        db = os.path.join(tmp, "w.db")
        _make_db(db, n=3)  # under MIN_PLAYS
        with wrapped_db(db):
            ed = wr.get_wrapped("week", llm=FakeLLM([{"content": "unused"}]))
            assert ed["empty"] is True


def test_period_bounds():
    from datetime import datetime, timezone
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

        with wrapped_db(db):
            s = wr.collect_stats("custom", start="2026-06-01", end="2026-06-10")
            assert s["plays"] == 23           # both boundary days included
            assert s["prev_plays"] == 5       # the 10 days before: only May 31
            assert s["label"].startswith("Jun 01")



if __name__ == "__main__":
    test_pipeline_generates_and_caches()
    test_reopening_shows_fresh_stats_and_drops_outdated_copy()
    test_reopening_keeps_copy_when_nothing_moved()
    test_generation_stops_when_the_budget_is_gone()
    test_invalid_style_falls_back_visibly()
    test_empty_period()
    test_period_bounds()
    test_custom_range_filters_inclusively()
    print("OK: all wrapped tests passed")
