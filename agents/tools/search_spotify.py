"""Spotify catalog search tool — read-only discovery beyond the history.

Lets the DJ reach tracks the user has NEVER played ("surprise me", "songs I
don't know"). Catalog search only — no account access, no writes. Results are
untrusted strings (track/artist names), same fencing rules as history data.
"""

import json

from integrations.spotify import auth_connection
from core.logging import configure_logger

logger = configure_logger(__name__)

MAX_LIMIT = 25

_client = None  # module-level cache: one OAuth client per process


def _sp():
    global _client
    if _client is None:
        _client = auth_connection()
    return _client


def _normalize_track(t):
    primary = (t.get("artists") or [{}])[0]
    return {
        "track_id": t.get("id"),
        "track_name": t.get("name"),
        "artist_name": primary.get("name"),
        "artist_id": primary.get("id"),
        "album_name": (t.get("album") or {}).get("name"),
        "duration_ms": t.get("duration_ms"),
        "popularity": t.get("popularity"),
    }


def search_spotify(args):
    """Tool entrypoint: catalog search (tracks or artists), normalized JSON."""
    query = (args.get("query") or "").strip()
    if not query:
        return json.dumps({"error": "Empty query."})
    search_type = args.get("type", "track")
    if search_type not in ("track", "artist", "playlist"):
        return json.dumps({"error": "type must be 'track', 'artist' or 'playlist'."})
    try:
        limit = max(1, min(int(args.get("limit", 10)), MAX_LIMIT))
    except (TypeError, ValueError):
        limit = 10

    sp = _sp()
    if not sp:
        return json.dumps({"error": "Spotify client unavailable."})
    try:
        res = sp.search(q=query, type=search_type, limit=limit)
    except Exception as exc:
        logger.warning("search_spotify failed for %r: %s", query, exc)
        return json.dumps({"error": f"{type(exc).__name__}: {exc}"})

    if search_type == "playlist":
        items = (res.get("playlists") or {}).get("items") or []
        playlists = [
            {
                "playlist_id": pl.get("id"),
                "name": pl.get("name"),
                "owner": (pl.get("owner") or {}).get("display_name"),
                "total_tracks": (pl.get("tracks") or {}).get("total"),
                "description": (pl.get("description") or "")[:120],
            }
            for pl in items if pl
        ]
        logger.info("search_spotify: %d playlists for %r", len(playlists), query)
        return json.dumps({"playlists": playlists, "count": len(playlists)})

    if search_type == "artist":
        items = (res.get("artists") or {}).get("items") or []
        artists = [
            {
                "artist_id": a.get("id"),
                "artist_name": a.get("name"),
                "genres": ", ".join(a.get("genres") or []),
                "popularity": a.get("popularity"),
            }
            for a in items if a
        ]
        logger.info("search_spotify: %d artists for %r", len(artists), query)
        return json.dumps({"artists": artists, "count": len(artists)})

    items = (res.get("tracks") or {}).get("items") or []
    tracks = [_normalize_track(t) for t in items if t]
    logger.info("search_spotify: %d tracks for %r", len(tracks), query)
    return json.dumps({"tracks": tracks, "count": len(tracks)})


def artist_top_tracks(args):
    """Tool entrypoint: an artist's top tracks (the discovery workhorse)."""
    artist_id = (args.get("artist_id") or "").strip()
    if not artist_id:
        return json.dumps({"error": "artist_id is required."})
    sp = _sp()
    if not sp:
        return json.dumps({"error": "Spotify client unavailable."})
    try:
        res = sp.artist_top_tracks(artist_id)
    except Exception as exc:
        logger.warning("artist_top_tracks failed for %r: %s", artist_id, exc)
        return json.dumps({"error": f"{type(exc).__name__}: {exc}"})
    tracks = [_normalize_track(t) for t in (res.get("tracks") or []) if t]
    logger.info("artist_top_tracks: %d tracks for %s", len(tracks), artist_id)
    return json.dumps({"tracks": tracks, "count": len(tracks)})


SEARCH_SPOTIFY_SCHEMA = {
    "type": "function",
    "function": {
        "name": "search_spotify",
        "description": (
            "Search the Spotify catalog — for songs the user has NEVER played "
            "(discovery), since query_history only sees their own history. "
            "type='track': free text or artist:\"Radiohead\" year:2020-2024. "
            "type='artist': find artists (genre filters ONLY work here, e.g. "
            "genre:\"israeli pop\") — then artist_top_tracks on the ids. "
            "type='playlist': find PUBLIC playlists by theme (e.g. 'hebrew "
            "upbeat hits') for candidate artists; discover_new_tracks mines them."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Search query."},
                "type": {
                    "type": "string",
                    "enum": ["track", "artist", "playlist"],
                    "description": "What to search for (default track).",
                },
                "limit": {
                    "type": "integer",
                    "description": f"Max results (1-{MAX_LIMIT}, default 10).",
                },
            },
            "required": ["query"],
        },
    },
}

ARTIST_TOP_TRACKS_SCHEMA = {
    "type": "function",
    "function": {
        "name": "artist_top_tracks",
        "description": (
            "Get an artist's most popular tracks by artist_id. The main "
            "discovery path: find artists (search_spotify type='artist' or "
            "history genres), then pull their top tracks."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "artist_id": {"type": "string", "description": "Spotify artist id."}
            },
            "required": ["artist_id"],
        },
    },
}
