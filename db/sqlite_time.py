from datetime import date, datetime, timedelta
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


def _local_date_value(played_at, tz_name):
    dt = _parse_played_at(played_at)
    if dt is None:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=ZoneInfo("UTC"))
    return dt.astimezone(ZoneInfo(tz_name)).date()


def local_date(played_at, tz_name):
    day = _local_date_value(played_at, tz_name)
    return day.isoformat() if day else None


def local_week_start(played_at, tz_name):
    day = _local_date_value(played_at, tz_name)
    if day is None:
        return None
    start = day - timedelta(days=(day.weekday() + 1) % 7)
    return start.isoformat()


def local_month_start(played_at, tz_name):
    day = _local_date_value(played_at, tz_name)
    if day is None:
        return None
    return date(day.year, day.month, 1).isoformat()


def register_time_udfs(conn):
    conn.create_function("local_hour", 2, local_hour)
    conn.create_function("local_weekday", 2, local_weekday)
    conn.create_function("local_date", 2, local_date)
    conn.create_function("local_week_start", 2, local_week_start)
    conn.create_function("local_month_start", 2, local_month_start)
