"""Database connections.

Returns ``(connection, driver_name)``; pair it with
``db.dialects.dialect_for(driver)`` for anything engine-specific.

Postgres is used whenever DATABASE_URL is set — the provider behind that URL
(Supabase, Neon, RDS, a local server) is irrelevant to this code. Without it,
a local SQLite file.
"""

import logging
import os
import sqlite3

from dotenv import load_dotenv

try:
    import psycopg2
except ImportError:
    psycopg2 = None

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

SQLITE_PATH = os.getenv("SQLITE_PATH", "my_spotify_data.db")

# Load .env here, not in callers: reading DATABASE_URL at import time made every
# local entrypoint that imported this before load_dotenv() ran silently fall
# back to SQLite while prod (real env var) used Postgres.
load_dotenv()


def get_db_connection(readonly=False):
    """Open a connection. `readonly=True` is enforced at the connection level,
    so no LLM-written SQL can mutate data."""
    db_url = os.getenv("DATABASE_URL")
    if db_url and psycopg2:
        return _connect_postgres(db_url, readonly)
    return _connect_sqlite(readonly)


def _connect_postgres(db_url, readonly):
    try:
        conn = psycopg2.connect(db_url)
        if readonly:
            conn.set_session(readonly=True)
        return conn, "postgres"
    except psycopg2.Error as exc:
        logger.error("Failed to connect to Postgres: %s", exc)
        return None, None


def _connect_sqlite(readonly):
    try:
        if readonly:
            conn = sqlite3.connect(f"file:{SQLITE_PATH}?mode=ro", uri=True)
        else:
            conn = sqlite3.connect(SQLITE_PATH)
        conn.row_factory = sqlite3.Row
        return conn, "sqlite"
    except sqlite3.Error as exc:
        logger.error("Failed to connect to SQLite: %s", exc)
        return None, None
