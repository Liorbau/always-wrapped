"""Durable per-run cost records behind the daily spend cap.

This lives in the database rather than on disk because the app runs on an
ephemeral filesystem: a file-based tally would silently reset the cap on every
deploy, which is the wrong direction for a spending guard to fail.
"""

import time

from db.connection import get_db_connection
from db.dialects import dialect_for
from core.logging import configure_logger

logger = configure_logger(__name__)


def _ensure_table(conn):
    conn.cursor().execute(
        """CREATE TABLE IF NOT EXISTS agent_run_cost (
            run_id TEXT PRIMARY KEY,
            day TEXT NOT NULL,
            kind TEXT NOT NULL,
            cost_usd REAL NOT NULL,
            recorded_at TEXT NOT NULL
        )"""
    )
    conn.commit()


def record(run_id, cost_usd, kind="agent", day=None):
    """Upsert one run's cost.

    A harness saves its log several times during a single run, so this
    overwrites the row instead of accumulating — otherwise one run would be
    counted once per save.
    """
    conn, driver = get_db_connection()
    if conn is None:
        logger.error("Run cost not recorded (no DB): %s $%.4f", run_id, cost_usd)
        return False

    try:
        _ensure_table(conn)
        p = dialect_for(driver).placeholder
        cursor = conn.cursor()
        now = time.strftime("%Y-%m-%dT%H:%M:%S")
        cursor.execute(
            f"UPDATE agent_run_cost SET cost_usd = {p}, kind = {p}, recorded_at = {p} "
            f"WHERE run_id = {p}",
            (float(cost_usd), kind, now, run_id),
        )
        if cursor.rowcount == 0:
            cursor.execute(
                "INSERT INTO agent_run_cost (run_id, day, kind, cost_usd, recorded_at) "
                f"VALUES ({p}, {p}, {p}, {p}, {p})",
                (run_id, day or time.strftime("%Y%m%d"), kind, float(cost_usd), now),
            )
        conn.commit()
        return True
    finally:
        conn.close()


def spent_on(day=None):
    """Total USD recorded for a YYYYMMDD day, or None when the DB is unreachable.

    None is distinct from 0.0 on purpose: the caller must not treat "unknown"
    as "nothing spent".
    """
    day = day or time.strftime("%Y%m%d")
    return spent_between(day, day)


def spent_between(start_day, end_day):
    """Total USD for days in [start_day, end_day] inclusive (YYYYMMDD).

    Returns None when the DB is unreachable — never invent a zero.
    """
    conn, driver = get_db_connection()
    if conn is None:
        logger.error("Spend range unavailable: no DB connection.")
        return None

    try:
        _ensure_table(conn)
        p = dialect_for(driver).placeholder
        cursor = conn.cursor()
        cursor.execute(
            f"SELECT COALESCE(SUM(cost_usd), 0) FROM agent_run_cost "
            f"WHERE day >= {p} AND day <= {p}",
            (start_day, end_day),
        )
        row = cursor.fetchone()
        return float(row[0]) if row and row[0] is not None else 0.0
    finally:
        conn.close()
