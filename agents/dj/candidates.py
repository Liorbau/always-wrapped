"""Where extra tracks come from when the model's pool falls short.

Two sources, both grounded: the user's own most-played history, and
never-played discoveries the DJ already fetched but didn't use.
"""

import json

from agents.dj import language
from db.connection import get_db_connection
from db.dialects import dialect_for

DEFAULT_GAP_LIMIT = 30
OVERFETCH_FACTOR = 4  # room to filter by script and still fill the limit


def gap_candidates(exclude_ids, limit=DEFAULT_GAP_LIMIT, hebrew_only=False):
    """Most-played history tracks not already in the playlist, with real data."""
    conn, driver = get_db_connection(readonly=True)
    if not conn:
        return []

    placeholder = dialect_for(driver).placeholder
    exclude_ids = [i for i in exclude_ids if i] or ["-"]
    cursor = conn.cursor()
    cursor.execute(
        f"""SELECT track_id, MAX(track_name), MAX(artist_name), MAX(duration_ms),
                   COUNT(*), MAX(artist_genres)
            FROM listening_history
            WHERE track_id IS NOT NULL AND duration_ms IS NOT NULL
              AND track_id NOT IN ({",".join([placeholder] * len(exclude_ids))})
            GROUP BY track_id ORDER BY COUNT(*) DESC
            LIMIT {int(limit) * OVERFETCH_FACTOR}""",
        exclude_ids,
    )
    rows = cursor.fetchall()
    conn.close()

    if hebrew_only:
        rows = [row for row in rows if language.is_hebrew(row[1])]
    return [
        f"{row[0]} | {row[1]} — {row[2]} | {row[3]} | {row[4]} plays | {row[5] or ''}"
        for row in rows[: int(limit)]
    ]


def unused_discoveries(dj, playlist, limit=40):
    """Verified-never-played candidates the DJ fetched but didn't use.

    Parsed back out of its own trajectory so a repair round can extend the pool
    without spending another tool call.
    """
    used = {t.get("track_id") for t in (playlist or {}).get("tracks") or []}
    found, seen = [], set()
    for entry in reversed(dj.trajectory if dj else []):
        if entry.get("type") != "tool_call" or entry.get("tool") != "discover_new_tracks":
            continue
        try:
            for line in json.loads(entry["result"]).get("tracks", []):
                track_id = line.split("|", 1)[0]
                if track_id not in used and track_id not in seen:
                    seen.add(track_id)
                    found.append(line)
        except (json.JSONDecodeError, KeyError):
            continue
    return found[:limit]
