"""Postgres RLS helper for Supabase-exposed backend tables.

Runnable directly:  ./venv/bin/python tests/test_rls.py
"""

import os
import sqlite3
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from tests import sandbox  # noqa: F401  — must precede every app import

from db.rls import enable_rls


def test_enable_rls_is_noop_on_sqlite():
    conn = sqlite3.connect(":memory:")
    cursor = conn.cursor()
    cursor.execute("CREATE TABLE playlist_timers (id INTEGER PRIMARY KEY)")
    enable_rls(cursor, "sqlite", "playlist_timers")
    cursor.execute("INSERT INTO playlist_timers VALUES (1)")
    assert cursor.execute("SELECT COUNT(*) FROM playlist_timers").fetchone()[0] == 1


if __name__ == "__main__":
    test_enable_rls_is_noop_on_sqlite()
    print("OK: all rls tests passed")
