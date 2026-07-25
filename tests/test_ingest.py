"""Checks for the ingest path: row flattening and schema migration.

Runnable directly (no framework needed):  python tests/test_ingest.py
Also discoverable by pytest.
"""

import os
import sqlite3
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from tests import sandbox  # noqa: F401  — must precede every app import

from pipelines.collector import build_track_row

SAMPLE_ITEM = {
    "played_at": "2026-07-07T10:00:00.000Z",
    "track": {
        "id": "track123",
        "name": "Some Song",
        "duration_ms": 215000,
        "album": {
            "name": "Some Album",
            "images": [{"url": "http://img/album.jpg"}],
            "release_date": "1977-02-04",
        },
        "artists": [{"id": "artist123", "name": "Some Artist"}],
    },
}

META = {"artist123": {"image_url": "http://img/artist.jpg", "genres": "pop, rock"}}


def test_build_track_row_full():
    row = build_track_row(SAMPLE_ITEM, META)
    assert row == (
        "2026-07-07T10:00:00.000Z",
        "track123",
        "Some Song",
        "Some Artist",
        "Some Album",
        "http://img/album.jpg",
        "artist123",
        "http://img/artist.jpg",
        215000,
        "pop, rock",
        "1977-02-04",
    )


def test_build_track_row_missing_optionals():
    item = {
        "played_at": "2026-07-07T11:00:00.000Z",
        "track": {
            "id": "t2",
            "name": "Bare Song",
            "album": {"name": "Bare Album", "images": []},
            "artists": [{"name": "No-ID Artist"}],  # no artist id
        },
    }
    row = build_track_row(item, META)
    assert row[3] == "No-ID Artist"
    assert row[5] is None  # no album image
    assert row[6] is None  # no artist id
    assert row[7] is None  # no artist image
    assert row[8] is None  # no duration
    assert row[9] is None  # no genres
    assert row[10] is None  # no release date


def test_migration_adds_new_columns():
    """A legacy-schema SQLite db gains duration_ms/artist_genres on setup."""
    import db.connection as db_config
    import db.schema as setup_db

    with tempfile.TemporaryDirectory() as tmp:
        path = os.path.join(tmp, "legacy.db")
        legacy = sqlite3.connect(path)
        legacy.execute(
            """CREATE TABLE listening_history (
                played_at TEXT PRIMARY KEY, track_id TEXT, track_name TEXT,
                artist_name TEXT, album_name TEXT, album_image_url TEXT)"""
        )
        legacy.commit()
        legacy.close()

        original = db_config.get_db_connection
        db_config.get_db_connection = lambda: (sqlite3.connect(path), "sqlite")
        setup_db.get_db_connection = db_config.get_db_connection
        try:
            setup_db.create_database()
        finally:
            db_config.get_db_connection = original
            setup_db.get_db_connection = original

        conn = sqlite3.connect(path)
        cols = {row[1] for row in conn.execute("PRAGMA table_info(listening_history)")}
        conn.close()
        for col in ("artist_id", "artist_image_url", "duration_ms", "artist_genres",
                    "album_release_date"):
            assert col in cols, f"missing migrated column: {col}"


if __name__ == "__main__":
    test_build_track_row_full()
    test_build_track_row_missing_optionals()
    test_migration_adds_new_columns()
    print("OK: all ingest tests passed")
