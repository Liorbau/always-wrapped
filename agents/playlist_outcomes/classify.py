"""Skip / completion inference from consecutive plays."""

from datetime import datetime

# gap < this × duration_ms → skip (matches "much smaller than duration" intent)
SKIP_FRAC = 0.5


def classify_gaps(plays):
    """plays: [{played_at, track_id, duration_ms}, ...] sorted ascending.

    Returns one row per play with outcome completed|skipped|unknown.
    Last play in a session has no next gap → unknown, not skip.
    """
    plays = sorted(plays or [], key=lambda p: p.get("played_at") or "")
    out = []
    for i, play in enumerate(plays):
        duration = play.get("duration_ms") or 0
        if i + 1 >= len(plays) or not duration:
            outcome = "unknown"
        else:
            gap_ms = gap_ms_between(play.get("played_at"), plays[i + 1].get("played_at"))
            if gap_ms is None:
                outcome = "unknown"
            elif gap_ms < SKIP_FRAC * duration:
                outcome = "skipped"
            else:
                outcome = "completed"
        out.append({
            "played_at": play.get("played_at"),
            "track_id": play.get("track_id"),
            "duration_ms": duration,
            "outcome": outcome,
        })
    return out


def gap_ms_between(a, b):
    sa, sb = parse_ts(a), parse_ts(b)
    if sa is None or sb is None:
        return None
    return max(0.0, (sb - sa) * 1000.0)


def seconds_between(a, b):
    sa, sb = parse_ts(a), parse_ts(b)
    if sa is None or sb is None:
        return None
    return round(max(0.0, sb - sa), 1)


def parse_ts(value):
    if not value:
        return None
    text = str(value).strip().replace("Z", "+00:00")
    if " " in text and "T" not in text:
        text = text.replace(" ", "T", 1)
    try:
        return datetime.fromisoformat(text).timestamp()
    except ValueError:
        return None
