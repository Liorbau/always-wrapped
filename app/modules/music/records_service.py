"""Personal listening records — measurable highs from listening_history."""

from calendar import monthrange
from datetime import date, timedelta

from app.modules.music import records_repository as repo

_LABELS = {
    "most_active_week": "Most active week",
    "most_active_month": "Most active month",
    "busiest_day": "Busiest day",
}


def _week_end(start):
    d = date.fromisoformat(start)
    return (d + timedelta(days=6)).isoformat()


def _month_end(start):
    d = date.fromisoformat(start)
    last = monthrange(d.year, d.month)[1]
    return date(d.year, d.month, last).isoformat()


def _record(kind, peak, window_end):
    return {
        "kind": kind,
        "label": _LABELS[kind],
        "value": peak["value"],
        "window_start": peak["window_start"],
        "window_end": window_end,
        "detail": f"{peak['value']} plays",
    }


def build(tz):
    records = []
    week = repo.most_active_week(tz)
    if week:
        records.append(_record("most_active_week", week, _week_end(week["window_start"])))
    month = repo.most_active_month(tz)
    if month:
        records.append(_record("most_active_month", month, _month_end(month["window_start"])))
    day = repo.busiest_day(tz)
    if day:
        records.append(_record("busiest_day", day, day["window_start"]))
    return records
