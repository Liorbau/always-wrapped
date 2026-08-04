"""DB reads used by outcome scoring (listening_history + bias cutoff)."""

from db.connection import get_db_connection
from db.dialects import dialect_for
from core.logging import configure_logger

logger = configure_logger(__name__)


def last_bias_update_at():
    conn, _driver = get_db_connection()
    if conn is None:
        return None
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT MAX(updated_at) FROM preference_bias")
        row = cursor.fetchone()
        return row[0] if row and row[0] else None
    except Exception:
        return None
    finally:
        conn.close()


def fetch_history_plays(since_iso, track_ids):
    """Plays for the given tracks on/after since_iso (inclusive)."""
    if not track_ids:
        return []
    conn, driver = get_db_connection()
    if conn is None:
        logger.error("Outcomes: no DB for listening_history.")
        return []
    try:
        dialect = dialect_for(driver)
        p = dialect.placeholder
        cursor = conn.cursor()
        placeholders = ", ".join(p for _ in track_ids)
        params = list(track_ids)
        sql = (
            "SELECT played_at, track_id, duration_ms FROM listening_history "
            f"WHERE track_id IN ({placeholders})"
        )
        if since_iso:
            sql += f" AND played_at >= {p}"
            params.append(since_iso)
        sql += " ORDER BY played_at ASC"
        cursor.execute(sql, params)
        return [
            {"played_at": row[0], "track_id": row[1], "duration_ms": row[2] or 0}
            for row in cursor.fetchall()
        ]
    except Exception as exc:
        logger.warning("Outcomes history query failed: %s", exc)
        return []
    finally:
        conn.close()
