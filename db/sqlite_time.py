from datetime import datetime
from zoneinfo import ZoneInfo


def _parse_played_at(text):
    if not text:
        return None
    value = text.strip()
    if value.endswith("Z"):
        value = value[:-1] + "+00:00"
    elif "T" in value and "+" not in value:
        value = value + "+00:00"
    return datetime.fromisoformat(value)


def local_hour(played_at, tz_name):
    dt = _parse_played_at(played_at)
    if dt is None:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=ZoneInfo("UTC"))
    return dt.astimezone(ZoneInfo(tz_name)).hour


def local_weekday(played_at, tz_name):
    dt = _parse_played_at(played_at)
    if dt is None:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=ZoneInfo("UTC"))
    return dt.astimezone(ZoneInfo(tz_name)).strftime("%A")


def register_time_udfs(conn):
    conn.create_function("local_hour", 2, local_hour)
    conn.create_function("local_weekday", 2, local_weekday)
