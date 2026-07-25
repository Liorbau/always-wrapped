"""The SQL dialect seam.

Both engines must expose the same surface, and the SQLite dialect's output has
to actually execute — these statements are built by string assembly, so a typo
would otherwise only surface in production.

Runnable directly:  ./venv/bin/python tests/test_dialects.py
"""

import os
import sqlite3
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from tests import sandbox  # noqa: F401  — must precede every app import

from db.dialects import DIALECTS, dialect_for
from db.dialects.base import Dialect
from db.dialects.postgres import PostgresDialect
from db.dialects.sqlite import SqliteDialect
from db.sqlite_time import register_time_udfs

SURFACE = ("hour_of", "weekday_name_of", "local_date", "local_week_start",
           "local_month_start", "within_last_days", "since_start_of_year",
           "insert_ignore", "upsert", "insert_returning_id", "inserted_id",
           "existing_columns")


def test_registry_resolves_and_rejects():
    assert isinstance(dialect_for("postgres"), PostgresDialect)
    assert isinstance(dialect_for("sqlite"), SqliteDialect)
    # already-resolved dialects pass through, so callers can hold either
    assert dialect_for(dialect_for("sqlite")) is dialect_for("sqlite")
    try:
        dialect_for("mysql")
    except ValueError as exc:
        assert "mysql" in str(exc)
    else:
        raise AssertionError("an unsupported driver was accepted")


def test_every_dialect_implements_the_whole_surface():
    for name, dialect in DIALECTS.items():
        assert isinstance(dialect, Dialect), name
        for method in SURFACE:
            assert callable(getattr(dialect, method)), f"{name} missing {method}"
        assert dialect.placeholder and dialect.timestamp_type and dialect.serial_pk


def test_placeholders_match_column_count():
    for dialect in DIALECTS.values():
        assert dialect.placeholders(3).count(dialect.placeholder) == 3


def test_dialects_disagree_where_they_must():
    postgres, sqlite = dialect_for("postgres"), dialect_for("sqlite")
    assert postgres.placeholder != sqlite.placeholder
    assert postgres.hour_of("played_at", "UTC") != sqlite.hour_of("played_at", "UTC")
    assert "INTERVAL" in postgres.within_last_days("played_at", 7)
    assert "datetime(" in sqlite.within_last_days("played_at", 7)
    assert "ON CONFLICT" in postgres.insert_ignore("t", ["a"], "a")
    assert "INSERT OR IGNORE" in sqlite.insert_ignore("t", ["a"], "a")
    assert "RETURNING id" in postgres.insert_returning_id("t", ["a"])
    assert "RETURNING" not in sqlite.insert_returning_id("t", ["a"])


def test_sqlite_generated_sql_actually_runs():
    dialect = dialect_for("sqlite")
    with tempfile.TemporaryDirectory() as tmp:
        conn = sqlite3.connect(os.path.join(tmp, "d.db"))
        cursor = conn.cursor()
        cursor.execute(
            f"CREATE TABLE notes (id {dialect.serial_pk}, body TEXT UNIQUE, "
            f"seen {dialect.timestamp_type})")

        # generated key round-trip
        cursor.execute(dialect.insert_returning_id("notes", ["body"]), ("first",))
        assert dialect.inserted_id(cursor) == 1

        # insert_ignore silently skips the duplicate
        cursor.execute(dialect.insert_ignore("notes", ["body"], "body"), ("first",))
        cursor.execute(dialect.insert_ignore("notes", ["body"], "body"), ("second",))
        assert cursor.execute("SELECT COUNT(*) FROM notes").fetchone()[0] == 2

        # upsert overwrites the conflicting row rather than adding one
        cursor.execute(
            dialect.upsert("notes", ["body", "seen"], conflict="body", updates=["seen"]),
            ("second", "2026-07-25"))
        assert cursor.execute("SELECT COUNT(*) FROM notes").fetchone()[0] == 2
        assert cursor.execute(
            "SELECT seen FROM notes WHERE body = 'second'").fetchone()[0] == "2026-07-25"

        assert dialect.existing_columns(cursor, "notes") == {"id", "body", "seen"}
        conn.close()


def test_sqlite_date_expressions_evaluate():
    dialect = dialect_for("sqlite")
    with tempfile.TemporaryDirectory() as tmp:
        conn = sqlite3.connect(os.path.join(tmp, "d.db"))
        register_time_udfs(conn)
        cursor = conn.cursor()
        cursor.execute("CREATE TABLE plays (played_at TEXT)")
        cursor.execute("INSERT INTO plays VALUES ('2026-07-20T14:30:00')")

        hour = cursor.execute(
            f"SELECT {dialect.hour_of('played_at', 'UTC')} FROM plays").fetchone()[0]
        assert hour == 14
        weekday = cursor.execute(
            f"SELECT {dialect.weekday_name_of('played_at', 'UTC')} FROM plays").fetchone()[0]
        assert weekday == "Monday"

        cursor.execute("DELETE FROM plays")
        cursor.execute("INSERT INTO plays VALUES ('2026-07-07T05:00:00Z')")
        hour = cursor.execute(
            f"SELECT {dialect.hour_of('played_at', 'Asia/Jerusalem')} FROM plays").fetchone()[0]
        assert hour == 8

        week_start = cursor.execute(
            f"SELECT {dialect.local_week_start('played_at', 'UTC')} FROM plays").fetchone()[0]
        assert week_start == "2026-07-05"
        month_start = cursor.execute(
            f"SELECT {dialect.local_month_start('played_at', 'UTC')} FROM plays").fetchone()[0]
        assert month_start == "2026-07-01"
        local_day = cursor.execute(
            f"SELECT {dialect.local_date('played_at', 'UTC')} FROM plays").fetchone()[0]
        assert local_day == "2026-07-07"

        # the predicates must be valid SQL even when they match nothing
        for predicate in (dialect.within_last_days("played_at", 7),
                          dialect.since_start_of_year("played_at")):
            cursor.execute(f"SELECT COUNT(*) FROM plays WHERE {predicate}")
        conn.close()


if __name__ == "__main__":
    test_registry_resolves_and_rejects()
    test_every_dialect_implements_the_whole_surface()
    test_placeholders_match_column_count()
    test_dialects_disagree_where_they_must()
    test_sqlite_generated_sql_actually_runs()
    test_sqlite_date_expressions_evaluate()
    print("OK: all dialect tests passed")
