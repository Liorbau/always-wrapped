"""Durable key/value settings the owner can change without a redeploy.

Read on the scheduler's hot path (once a minute), so every access is a single
primary-key lookup. A missing connection raises rather than returning the
default: a silent fallback here would look exactly like "the owner never set
this", which is a different state with different behaviour.
"""

from db.connection import get_db_connection
from db.dialects import dialect_for
from db.rls import enable_rls


def _conn():
    conn, driver = get_db_connection()
    if conn is None:
        raise RuntimeError("No database connection.")
    cursor = conn.cursor()
    cursor.execute("""CREATE TABLE IF NOT EXISTS app_settings (
        key TEXT PRIMARY KEY,
        value TEXT)""")
    enable_rls(cursor, driver, "app_settings")
    conn.commit()
    return conn, driver


def get(key, default=None):
    conn, driver = _conn()
    try:
        cursor = conn.cursor()
        cursor.execute(
            f"SELECT value FROM app_settings WHERE key = {dialect_for(driver).placeholder}",
            (key,))
        row = cursor.fetchone()
        return row[0] if row else default
    finally:
        conn.close()


def set_value(key, value):
    conn, driver = _conn()
    try:
        conn.cursor().execute(
            dialect_for(driver).upsert(
                "app_settings", ["key", "value"], conflict="key", updates=["value"]),
            (key, value))
        conn.commit()
    finally:
        conn.close()
