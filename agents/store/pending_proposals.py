"""Durable pending playlist proposals (pre-Approve lifecycle).

Survives process restart. Single-use: approve/reject flip status atomically so
a replay cannot push twice. Spotify failure restores `pending` for an explicit
retry. Expiry is checked at claim time (TTL_HOURS).
"""

import json
import uuid
from datetime import datetime, timedelta, timezone

from db.connection import get_db_connection
from db.dialects import dialect_for
from db.rls import enable_rls
from core.logging import configure_logger

logger = configure_logger(__name__)

TTL_HOURS = 24
PENDING = "pending"
APPROVED = "approved"
REJECTED = "rejected"
EXPIRED = "expired"


def _now():
    return datetime.now(timezone.utc)


def _iso(dt):
    return dt.strftime("%Y-%m-%dT%H:%M:%SZ")


def _parse(ts):
    if not ts:
        return None
    value = ts.strip()
    if value.endswith("Z"):
        value = value[:-1] + "+00:00"
    return datetime.fromisoformat(value)


def _conn():
    conn, driver = get_db_connection()
    if conn is None:
        raise RuntimeError("No database connection.")
    cursor = conn.cursor()
    cursor.execute(
        """CREATE TABLE IF NOT EXISTS pending_proposal (
            id TEXT PRIMARY KEY,
            playlist TEXT NOT NULL,
            status TEXT NOT NULL,
            created_at TEXT NOT NULL,
            expires_at TEXT NOT NULL,
            decided_at TEXT
        )"""
    )
    enable_rls(cursor, driver, "pending_proposal")
    conn.commit()
    return conn, driver


def insert(playlist, proposal_id=None):
    proposal_id = proposal_id or uuid.uuid4().hex
    now = _now()
    conn, driver = _conn()
    p = dialect_for(driver).placeholder
    try:
        conn.cursor().execute(
            f"INSERT INTO pending_proposal (id, playlist, status, created_at, expires_at) "
            f"VALUES ({p}, {p}, {p}, {p}, {p})",
            (proposal_id, json.dumps(playlist, ensure_ascii=False), PENDING,
             _iso(now), _iso(now + timedelta(hours=TTL_HOURS))),
        )
        conn.commit()
    finally:
        conn.close()
    return proposal_id


def _load(cursor, driver, proposal_id):
    p = dialect_for(driver).placeholder
    cursor.execute(
        f"SELECT id, playlist, status, created_at, expires_at, decided_at "
        f"FROM pending_proposal WHERE id = {p}",
        (proposal_id,),
    )
    row = cursor.fetchone()
    if not row:
        return None
    return {
        "id": row[0],
        "playlist": json.loads(row[1]),
        "status": row[2],
        "created_at": row[3],
        "expires_at": row[4],
        "decided_at": row[5],
    }


def claim(proposal_id, to_status):
    """Atomically move a still-valid pending row to approved/rejected.

    Returns the playlist, or None if missing / already decided / expired.
    """
    if to_status not in (APPROVED, REJECTED):
        raise ValueError(to_status)
    conn, driver = _conn()
    p = dialect_for(driver).placeholder
    now = _now()
    try:
        cursor = conn.cursor()
        row = _load(cursor, driver, proposal_id)
        if row is None:
            return None
        if row["status"] != PENDING:
            return None
        if _parse(row["expires_at"]) <= now:
            cursor.execute(
                f"UPDATE pending_proposal SET status = {p}, decided_at = {p} "
                f"WHERE id = {p} AND status = {p}",
                (EXPIRED, _iso(now), proposal_id, PENDING),
            )
            conn.commit()
            return None
        cursor.execute(
            f"UPDATE pending_proposal SET status = {p}, decided_at = {p} "
            f"WHERE id = {p} AND status = {p}",
            (to_status, _iso(now), proposal_id, PENDING),
        )
        if cursor.rowcount != 1:
            conn.commit()
            return None
        conn.commit()
        return row["playlist"]
    finally:
        conn.close()


def restore_pending(proposal_id):
    """After a Spotify failure — proposal is approvable again."""
    conn, driver = _conn()
    p = dialect_for(driver).placeholder
    try:
        conn.cursor().execute(
            f"UPDATE pending_proposal SET status = {p}, decided_at = NULL "
            f"WHERE id = {p} AND status = {p}",
            (PENDING, proposal_id, APPROVED),
        )
        conn.commit()
    finally:
        conn.close()


def is_pending(proposal_id):
    conn, driver = _conn()
    try:
        row = _load(conn.cursor(), driver, proposal_id)
    finally:
        conn.close()
    if row is None or row["status"] != PENDING:
        return False
    return _parse(row["expires_at"]) > _now()


def pending_playlists():
    """id -> playlist for still-valid pending rows (tests / diagnostics)."""
    conn, driver = _conn()
    p = dialect_for(driver).placeholder
    now = _now()
    try:
        cursor = conn.cursor()
        cursor.execute(
            f"SELECT id, playlist, expires_at FROM pending_proposal WHERE status = {p}",
            (PENDING,),
        )
        out = {}
        for proposal_id, blob, expires_at in cursor.fetchall():
            if _parse(expires_at) > now:
                out[proposal_id] = json.loads(blob)
        return out
    finally:
        conn.close()


def delete(proposal_id):
    conn, driver = _conn()
    p = dialect_for(driver).placeholder
    try:
        conn.cursor().execute(
            f"DELETE FROM pending_proposal WHERE id = {p}", (proposal_id,))
        conn.commit()
    finally:
        conn.close()


def clear():
    conn, _driver = _conn()
    try:
        conn.cursor().execute("DELETE FROM pending_proposal")
        conn.commit()
    finally:
        conn.close()
