"""Durable record of every human approve/reject decision.

This is the Evaluator's entire training signal and the Wrapped pipeline's view
of what the DJ actually shipped, so it cannot live in a file the next deploy
erases.
"""

import json
import time
import uuid

from db.connection import get_db_connection
from db.dialects import dialect_for
from core.logging import configure_logger

logger = configure_logger(__name__)

PUSHED = "pushed"
REJECTED = "rejected"

MAX_REASON_CHARS = 500


def _ensure_table(conn):
    conn.cursor().execute(
        """CREATE TABLE IF NOT EXISTS hitl_decision (
            id TEXT PRIMARY KEY,
            ts TEXT NOT NULL,
            decision TEXT NOT NULL,
            reason TEXT,
            playlist_url TEXT,
            playlist TEXT NOT NULL
        )"""
    )
    conn.commit()


def record_push(playlist, url, ts=None, record_id=None):
    return _record(PUSHED, playlist, url=url, ts=ts, record_id=record_id)


def record_rejection(playlist, reason, ts=None, record_id=None):
    return _record(
        REJECTED, playlist,
        reason=(reason or "").strip()[:MAX_REASON_CHARS], ts=ts, record_id=record_id,
    )


def _record(decision, playlist, url=None, reason=None, ts=None, record_id=None):
    """`record_id` makes a write idempotent, which the backfill script relies on."""
    conn, driver = get_db_connection()
    if conn is None:
        logger.error("HITL %s not recorded (no DB): %s",
                     decision, (playlist or {}).get("name"))
        return False

    try:
        _ensure_table(conn)
        p = dialect_for(driver).placeholder
        cursor = conn.cursor()
        values = (ts or time.strftime("%Y-%m-%dT%H:%M:%S"), decision, reason, url,
                  json.dumps(playlist, ensure_ascii=False))

        if record_id:
            cursor.execute(
                f"UPDATE hitl_decision SET ts = {p}, decision = {p}, reason = {p}, "
                f"playlist_url = {p}, playlist = {p} WHERE id = {p}",
                values + (record_id,),
            )
            if cursor.rowcount:
                conn.commit()
                return True

        cursor.execute(
            "INSERT INTO hitl_decision (id, ts, decision, reason, playlist_url, playlist) "
            f"VALUES ({p}, {p}, {p}, {p}, {p}, {p})",
            (record_id or uuid.uuid4().hex,) + values,
        )
        conn.commit()
        return True
    finally:
        conn.close()


def recent(decision, limit=10):
    """The newest decisions of one kind, returned oldest-first so the Evaluator
    reads them as a timeline."""
    return _select(f"decision = {{p}} ORDER BY ts DESC LIMIT {int(limit)}", (decision,),
                   reverse=True)


def pushes_since(iso_ts):
    """Pushed playlists on or after an ISO timestamp (or plain YYYY-MM-DD date)."""
    return _select("decision = {p} AND ts >= {p} ORDER BY ts ASC", (PUSHED, iso_ts))


def _select(where, params, reverse=False):
    conn, driver = get_db_connection()
    if conn is None:
        logger.error("HITL history unavailable: no DB connection.")
        return []

    try:
        _ensure_table(conn)
        p = dialect_for(driver).placeholder
        cursor = conn.cursor()
        cursor.execute(
            "SELECT ts, reason, playlist_url, playlist FROM hitl_decision "
            "WHERE " + where.format(p=p),
            params,
        )
        rows = cursor.fetchall()
    finally:
        conn.close()

    if reverse:
        rows = list(reversed(rows))
    return [_to_dict(row) for row in rows]


def _to_dict(row):
    try:
        playlist = json.loads(row[3])
    except (TypeError, ValueError):
        playlist = {}
    return {"ts": row[0], "reason": row[1], "url": row[2], "playlist": playlist}
