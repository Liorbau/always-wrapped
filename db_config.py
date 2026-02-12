"""Database connection helpers.

This module provides `get_db_connection()` which returns a connection
and a driver name tuple ("postgres" or "sqlite"). It also provides
`get_placeholder()` to get the SQL parameter placeholder for the
active driver.
"""

import os
import sqlite3
import logging

try:
    import psycopg2
except ImportError:
    psycopg2 = None

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

DB_URL = os.getenv("DATABASE_URL")


def get_db_connection():
    """
    Returns a database connection.
    If DATABASE_URL exists - connects to Postgres (Supabase).
    If not - connects to local SQLite.
    """
    if DB_URL and psycopg2:
        try:
            conn = psycopg2.connect(DB_URL)
            return conn, "postgres"
        except psycopg2.Error as e:
            logger.error("Failed to connect to Postgres: %s", e)
            return None, None
    else:
        try:
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
