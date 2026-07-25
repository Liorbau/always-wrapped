"""Peak listening windows aggregated from listening_history."""

from app.modules.music.repository import cursor_for
from db.dialects import dialect_for


def _as_date_str(value):
    if value is None:
        return None
    if hasattr(value, "isoformat"):
        return value.isoformat()
    return str(value)[:10]


def _peak_group(tz, group_builder):
    with cursor_for(readonly=True) as (cursor, driver):
        group_expr = group_builder(dialect_for(driver))
        cursor.execute(
            f"""
            SELECT {group_expr} AS window_start, COUNT(*) AS play_count
            FROM listening_history
            WHERE {group_expr} IS NOT NULL
            GROUP BY window_start
            ORDER BY play_count DESC, window_start DESC
            LIMIT 1
            """
        )
        row = cursor.fetchone()
        if not row or row[0] is None:
            return None
        return {"window_start": _as_date_str(row[0]), "value": int(row[1])}


def most_active_week(tz):
    return _peak_group(tz, lambda d: d.local_week_start("played_at", tz))


def most_active_month(tz):
    return _peak_group(tz, lambda d: d.local_month_start("played_at", tz))


def busiest_day(tz):
    return _peak_group(tz, lambda d: d.local_date("played_at", tz))
