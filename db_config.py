import os
import sqlite3
import logging
try:
    import psycopg2
    from psycopg2.extras import RealDictCursor
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
        except Exception as e:
            logger.error(f"Failed to connect to Postgres: {e}")
            return None, None
    else:
        try:
            conn = sqlite3.connect("my_spotify_data.db")
            conn.row_factory = sqlite3.Row
            return conn, "sqlite"
        except Exception as e:
            logger.error(f"Failed to connect to SQLite: {e}")
            return None, None

def get_placeholder(driver):
    return "%s" if driver == "postgres" else "?"