"""Macro discovery tool: wide reach in ONE call, mechanics done in code.

Mines the top public playlists for a theme, dedupes, filters out everything
already in the listening history (the 0-plays verification the model used to
burn steps on), and returns a compact verified-never-played candidate list.
One call replaces ~6-8 tool calls and ~9k tokens of raw playlist JSON.
"""

import json

from agents.tools.search_spotify import _normalize_track, _sp
from db.connection import get_db_connection
from db.dialects import dialect_for
from core.logging import configure_logger

logger = configure_logger(__name__)

MAX_RETURN = 60
PLAYLISTS_TO_MINE = 3


def discover_new_tracks(args):
    """Tool entrypoint: theme query -> compact list of verified-unplayed tracks."""
    query = (args.get("query") or "").strip()
    if not query:
        return json.dumps({"error": "query is required."})
    try:
        limit = max(1, min(int(args.get("limit", MAX_RETURN)), MAX_RETURN))
    except (TypeError, ValueError):
        limit = MAX_RETURN

    sp = _sp()
    if not sp:
        return json.dumps({"error": "Spotify client unavailable."})
    try:
        res = sp.search(q=query, type="playlist", limit=8)
    except Exception as exc:
        return json.dumps({"error": f"{type(exc).__name__}: {exc}"})
    playlists = [pl for pl in (res.get("playlists") or {}).get("items") or [] if pl]
    playlists = playlists[:PLAYLISTS_TO_MINE]
    if not playlists:
        return json.dumps({"error": f"No public playlists found for {query!r} — "
                                    "try a broader theme."})

    candidates = {}
    for pl in playlists:
        try:
            items = sp.playlist_items(pl["id"], limit=100)
        except Exception as exc:
            logger.warning("discover: playlist %s failed: %s", pl.get("id"), exc)
            continue
        for item in items.get("items") or []:
            track = (item or {}).get("track")
            if track and track.get("id") and track["id"] not in candidates:
                candidates[track["id"]] = _normalize_track(track)

    if not candidates:
        return json.dumps({"error": "Playlists were empty or unreadable."})

    # 0-plays verification in code: drop everything the user already played
    conn, driver = get_db_connection(readonly=True)
    played = set()
    if conn:
        p = dialect_for(driver).placeholder
        cursor = conn.cursor()
        ids = list(candidates)
        for i in range(0, len(ids), 200):
            chunk = ids[i : i + 200]
            cursor.execute(
                f"""SELECT DISTINCT track_id FROM listening_history
                    WHERE track_id IN ({",".join([p] * len(chunk))})""",
                chunk,
            )
            played.update(row[0] for row in cursor.fetchall())
        conn.close()

    fresh = [t for tid, t in candidates.items() if tid not in played][:limit]
    lines = [f"{t['track_id']}|{t['track_name']}|{t['artist_name']}|{t['duration_ms']}"
             for t in fresh]
    logger.info("discover: %d playlists -> %d candidates -> %d never-played",
                len(playlists), len(candidates), len(lines))
    return json.dumps({
        "count": len(lines),
        "verified_never_played": True,
        "format": "track_id|title|artist|duration_ms",
        "tracks": lines,
        "playlists_mined": [pl.get("name") for pl in playlists],
        "already_played_removed": len(played),
    }, ensure_ascii=False)


DISCOVER_SCHEMA = {
    "type": "function",
    "function": {
        "name": "discover_new_tracks",
        "description": (
            "THE tool for never-played requests: one call mines top public "
            "playlists for a theme (e.g. 'upbeat hebrew hits'), removes every "
            "track the user already played (verified in the database), and "
            "returns up to 60 compact candidates with real durations. No "
            "further 0-plays checking needed."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Theme/mood/genre to mine."},
                "limit": {"type": "integer",
                          "description": f"Max candidates (default {MAX_RETURN})."},
            },
            "required": ["query"],
        },
    },
}
