"""Tests for the guarded read-only SQL tool — no network, temp SQLite only.

Runnable directly:  ./venv/bin/python tests/test_tools.py
"""

import json
import os
import sqlite3
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from tests import sandbox  # noqa: F401  — must precede every app import

import importlib

# the package re-exports the query_history *function*, which shadows the
# module attribute — importlib gets us the real module for monkeypatching
qh = importlib.import_module("agents.tools.query_history")
from agents.tools import validate_sql, query_history, TOOL_REGISTRY


def make_db(path, n_rows=5):
    conn = sqlite3.connect(path)
    conn.execute(
        """CREATE TABLE listening_history (
            played_at TEXT PRIMARY KEY, track_id TEXT, track_name TEXT,
            artist_name TEXT, album_name TEXT, album_image_url TEXT,
            artist_id TEXT, artist_image_url TEXT,
            duration_ms INTEGER, artist_genres TEXT)"""
    )
    for i in range(n_rows):
        conn.execute(
            "INSERT INTO listening_history (played_at, track_id, track_name, artist_name, duration_ms, artist_genres)"
            " VALUES (?, ?, ?, ?, ?, ?)",
            (f"2026-07-0{i % 9 + 1}T10:00:{i:02d}Z", f"t{i}", f"Song {i}", f"Artist {i % 3}", 200000, "pop"),
        )
    conn.commit()
    conn.close()


def patched_connection(path):
    def _connect(readonly=False):
        mode = f"file:{path}?mode=ro" if readonly else path
        conn = sqlite3.connect(mode, uri=readonly)
        return conn, "sqlite"
    return _connect


def test_validate_sql_guard():
    assert validate_sql("SELECT * FROM listening_history") is None
    for bad in (
        "INSERT INTO listening_history VALUES (1)",
        "UPDATE listening_history SET track_name='x'",
        "DELETE FROM listening_history",
        "DROP TABLE listening_history",
        "PRAGMA table_info(listening_history)",
        "SELECT 1; DROP TABLE listening_history",
        "CREATE TABLE evil (x)",
        "",
    ):
        assert validate_sql(bad) is not None, f"guard let through: {bad!r}"


def test_allowlist_keeps_real_history_queries_working():
    for sql in (
        "SELECT * FROM listening_history",
        "SELECT * FROM listening_history h JOIN listening_history g ON h.track_id = g.track_id",
        "WITH recent AS (SELECT * FROM listening_history) SELECT * FROM recent",
        "WITH a AS (SELECT * FROM listening_history LIMIT 1) "
        "SELECT * FROM a",
        "SELECT EXTRACT(HOUR FROM played_at) FROM listening_history",
        "SELECT substr(album_release_date, 1, 4) FROM listening_history",
        "SELECT * FROM (SELECT track_id FROM listening_history) t",
        "SELECT track_name FROM listening_history WHERE artist_name = 'FROM preference_bias'",
    ):
        assert validate_sql(sql) is None, f"guard wrongly rejected: {sql!r}"


def test_allowlist_blocks_every_other_table():
    for sql in (
        "SELECT * FROM preference_bias",
        "SELECT * FROM listening_history, preference_bias",
        "SELECT * FROM listening_history , hitl_decision",
        "SELECT track_id FROM listening_history UNION SELECT run_id FROM agent_run_cost",
        "SELECT * FROM listening_history JOIN playlist_timers ON 1=1",
        "SELECT * FROM information_schema.columns",
        "SELECT * FROM sqlite_master",
        "SELECT * FROM public.listening_history",
        # comments must not hide the real table from the scanner
        "SELECT * FROM /* listening_history */ preference_bias",
        "SELECT * FROM listening_history /* x */ JOIN agent_run_cost ON 1=1",
    ):
        error = validate_sql(sql)
        assert error is not None, f"guard let through: {sql!r}"
        assert "not available" in error or "Forbidden" in error


def test_require_listening_history_blocks_fromless():
    for sql in (
        "SELECT 1",
        "SELECT pg_sleep(30)",
        "SELECT version()",
        "SELECT current_setting('is_superuser')",
        "SELECT pg_read_file('/etc/passwd')",
        "WITH x AS (SELECT 1) SELECT * FROM x",
        "WITH a AS (SELECT 1), b AS (SELECT 2) SELECT * FROM a JOIN b ON 1=1",
    ):
        error = validate_sql(sql)
        assert error is not None, f"guard let through: {sql!r}"
        assert "listening_history" in error.lower()


def test_query_returns_rows():
    with tempfile.TemporaryDirectory() as tmp:
        path = os.path.join(tmp, "t.db")
        make_db(path)
        original = qh.get_db_connection
        qh.get_db_connection = patched_connection(path)
        try:
            out = json.loads(query_history({"sql": "SELECT artist_name, COUNT(*) c FROM listening_history GROUP BY 1 ORDER BY c DESC"}))
            assert out["columns"] == ["artist_name", "c"]
            assert out["row_count"] == 3
            assert not out["truncated"]

            # bad SQL comes back as a correctable error, not a crash
            err = json.loads(query_history({"sql": "SELECT nope FROM listening_history"}))
            assert "error" in err

            # write attempts are rejected by the guard, embedded or leading
            rej = json.loads(query_history({"sql": "DELETE FROM listening_history"}))
            assert "Only SELECT" in rej["error"]
            rej = json.loads(query_history({"sql": "SELECT 1 UNION SELECT 2; DROP TABLE listening_history"}))
            assert "error" in rej
        finally:
            qh.get_db_connection = original


def test_row_cap():
    with tempfile.TemporaryDirectory() as tmp:
        path = os.path.join(tmp, "t.db")
        make_db(path, n_rows=250)
        original = qh.get_db_connection
        qh.get_db_connection = patched_connection(path)
        try:
            out = json.loads(query_history({"sql": "SELECT track_id FROM listening_history"}))
            assert out["row_count"] == qh.MAX_ROWS
            assert out["truncated"]
        finally:
            qh.get_db_connection = original


class FakeSpotify:
    def __init__(self, items, playlists=None, playlist_items=None):
        self.items = items
        self.playlists = playlists or []
        self._playlist_items = playlist_items or []
        self.queries = []

    def search(self, q, type, limit):
        self.queries.append((q, limit))
        if type == "playlist":
            return {"playlists": {"items": self.playlists[:limit]}}
        return {"tracks": {"items": self.items[:limit]}}

    def playlist_items(self, playlist_id, limit):
        return {"items": self._playlist_items[:limit]}


def test_search_spotify_normalizes_results():
    # function re-export shadows the module (see qh above) — importlib required
    ss = importlib.import_module("agents.tools.search_spotify")
    ss._client = FakeSpotify([{
        "id": "abc", "name": "New Song", "duration_ms": 180000, "popularity": 55,
        "album": {"name": "New Album"},
        "artists": [{"id": "art1", "name": "Fresh Artist"}],
    }])
    try:
        out = json.loads(TOOL_REGISTRY["search_spotify"]({"query": 'genre:"indie"'}))
        assert out["count"] == 1
        track = out["tracks"][0]
        assert track == {"track_id": "abc", "track_name": "New Song",
                         "artist_name": "Fresh Artist", "artist_id": "art1",
                         "album_name": "New Album", "duration_ms": 180000,
                         "popularity": 55}
        # empty query rejected without an API call
        err = json.loads(TOOL_REGISTRY["search_spotify"]({"query": "  "}))
        assert "error" in err
        # limit clamped to MAX_LIMIT
        json.loads(TOOL_REGISTRY["search_spotify"]({"query": "x", "limit": 999}))
        assert ss._client.queries[-1][1] == ss.MAX_LIMIT
    finally:
        ss._client = None


def test_readonly_connection_blocks_writes():
    """Even if the statement guard were bypassed, the connection refuses writes."""
    with tempfile.TemporaryDirectory() as tmp:
        path = os.path.join(tmp, "t.db")
        make_db(path)
        conn, _ = patched_connection(path)(readonly=True)
        try:
            conn.execute("INSERT INTO listening_history (played_at) VALUES ('x')")
            raise AssertionError("read-only connection accepted a write")
        except sqlite3.OperationalError:
            pass
        finally:
            conn.close()


def test_playlist_search_and_mining():
    ss = importlib.import_module("agents.tools.search_spotify")
    track = {"id": "pt1", "name": "Curated Song", "duration_ms": 180000,
             "popularity": 40, "album": {"name": "A"},
             "artists": [{"id": "a1", "name": "Curator's Pick"}]}
    ss._client = FakeSpotify(
        [],
        playlists=[{"id": "pl9", "name": "Hebrew Happy Hits",
                    "owner": {"display_name": "someone"},
                    "tracks": {"total": 87}, "description": "x" * 300},
                   None],  # Spotify search returns null items sometimes
        playlist_items=[{"track": track},
                        {"track": None},                       # local file
                        {"track": {"id": None, "name": "ep"}}])  # podcast episode
    try:
        out = json.loads(TOOL_REGISTRY["search_spotify"](
            {"query": "hebrew happy", "type": "playlist"}))
        assert out["count"] == 1
        assert out["playlists"][0]["playlist_id"] == "pl9"
        assert out["playlists"][0]["total_tracks"] == 87
        assert len(out["playlists"][0]["description"]) <= 120
    finally:
        ss._client = None


def test_discover_new_tracks_filters_played():
    import agents.tools.discover as dv
    ss = importlib.import_module("agents.tools.search_spotify")
    mk = lambda i: {"id": f"d{i}", "name": f"Fresh {i}", "duration_ms": 180000,
                    "popularity": 10, "album": {"name": "A"},
                    "artists": [{"id": "a", "name": "Artist"}]}
    ss._client = FakeSpotify(
        [], playlists=[{"id": "pl1", "name": "Hebrew Hits",
                        "owner": {"display_name": "x"}, "tracks": {"total": 4},
                        "description": ""}],
        playlist_items=[{"track": mk(i)} for i in range(4)])
    with tempfile.TemporaryDirectory() as tmp:
        path = os.path.join(tmp, "t.db")
        make_db(path, n_rows=0)
        conn = sqlite3.connect(path)
        conn.execute("INSERT INTO listening_history (played_at, track_id) VALUES ('2026-01-01T00:00:00Z', 'd1')")
        conn.commit(); conn.close()
        original = dv.get_db_connection
        dv.get_db_connection = patched_connection(path)
        try:
            out = json.loads(TOOL_REGISTRY["discover_new_tracks"]({"query": "hebrew hits"}))
        finally:
            dv.get_db_connection = original
            ss._client = None
    assert out["count"] == 3                       # d1 already played -> removed
    assert out["already_played_removed"] == 1
    assert all("|" in line for line in out["tracks"])   # compact format
    assert not any(line.startswith("d1|") for line in out["tracks"])
    err = json.loads(TOOL_REGISTRY["discover_new_tracks"]({}))
    assert "error" in err


def test_audio_features_maps_spotify_ids():
    import agents.tools.audio_features as af

    class FakeResp:
        status_code = 200
        def raise_for_status(self): pass
        def json(self):
            return {"content": [{
                "id": "rb-uuid", "href": "https://open.spotify.com/track/sp123",
                "energy": 0.75, "valence": 0.6, "danceability": 0.3,
                "tempo": 97.0, "acousticness": 0.01, "loudness": -5.7,
                "key": 4, "mode": 1}]}

    original = af.requests.get
    af.requests.get = lambda *a, **k: FakeResp()
    try:
        out = json.loads(af.get_audio_features({"track_ids": ["sp123", "sp-missing"]}))
    finally:
        af.requests.get = original
    assert out["features"]["sp123"]["energy"] == 0.75
    assert out["features"]["sp123"]["loudness"] == -5.7
    assert "key" not in out["features"]["sp123"]   # theory fields stay dropped
    assert out["missing"] == ["sp-missing"]
    err = json.loads(af.get_audio_features({"track_ids": []}))
    assert "error" in err


if __name__ == "__main__":
    test_validate_sql_guard()
    test_allowlist_keeps_real_history_queries_working()
    test_allowlist_blocks_every_other_table()
    test_require_listening_history_blocks_fromless()
    test_query_returns_rows()
    test_row_cap()
    test_readonly_connection_blocks_writes()
    test_search_spotify_normalizes_results()
    test_playlist_search_and_mining()
    test_discover_new_tracks_filters_played()
    test_audio_features_maps_spotify_ids()
    print("OK: all tools tests passed")
