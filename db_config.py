"""Database connection helpers.

This module provides `get_db_connection()` which returns a connection
and a driver name tuple ("postgres" or "sqlite"). It also provides
`get_placeholder()` to get the SQL parameter placeholder for the
active driver.
"""

import os
import sqlite3
import logging

from dotenv import load_dotenv

try:
    import psycopg2
except ImportError:
    psycopg2 = None

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Load .env here, not in callers: reading DATABASE_URL at import time made
# every local entrypoint that imported db_config before load_dotenv() ran
# silently fall back to SQLite while prod (real env var) used Postgres.
load_dotenv()


def get_db_connection(readonly=False):
    """
    Returns a database connection.
    If DATABASE_URL exists - connects to Postgres (Supabase).
    If not - connects to local SQLite.

    readonly=True enforces read-only at the connection level (used by
    agent tools so no LLM-written SQL can ever mutate data).
    """
    db_url = os.getenv("DATABASE_URL")
    if db_url and psycopg2:
        try:
            conn = psycopg2.connect(db_url)
            if readonly:
                conn.set_session(readonly=True)
            return conn, "postgres"
        except psycopg2.Error as e:
            logger.error("Failed to connect to Postgres: %s", e)
            return None, None
    else:
        try:
            if readonly:
                conn = sqlite3.connect("file:my_spotify_data.db?mode=ro", uri=True)
            else:
                conn = sqlite3.connect("my_spotify_data.db")
            conn.row_factory = sqlite3.Row
            return conn, "sqlite"
        except sqlite3.Error as e:
            logger.error("Failed to connect to SQLite: %s", e)
            return None, None


def get_placeholder(driver):
    """Return the SQL parameter placeholder for the given driver.

    Args:
        driver (str): Either "postgres" or "sqlite" (or other).

    Returns:
        str: Parameter placeholder ("%s" for Postgres, "?" otherwise).
    """

    return "%s" if driver == "postgres" else "?"
