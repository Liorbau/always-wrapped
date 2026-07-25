"""Real artist, duration and play count per track id.

History first; ids the history has never seen are resolved against the Spotify
catalog (never-played discovery picks). Ids unknown to both are simply absent,
which is how the verifier detects a hallucinated id.
"""

from db.connection import get_db_connection
from db.dialects import dialect_for
from core.logging import configure_logger

logger = configure_logger(__name__)

SPOTIFY_BATCH = 50


def spotify_track_info(ids):
    from integrations.spotify import auth_connection

    sp = auth_connection()
    if not sp or not ids:
        return {}

    info = {}
    try:
        for start in range(0, len(ids), SPOTIFY_BATCH):
            response = sp.tracks(ids[start : start + SPOTIFY_BATCH])
            for track in response.get("tracks") or []:
                if not track:
                    continue
                primary = (track.get("artists") or [{}])[0]
                info[track["id"]] = {
                    "artist": primary.get("name"),
                    "duration_ms": track.get("duration_ms"),
                    "plays": 0,
                }
    except Exception as exc:
        logger.warning("Spotify ground-truth lookup failed: %s", exc)
    return info


def reality(tracks):
    """Returns {track_id: {artist, duration_ms, plays}}, or None if the DB is down."""
    ids = [t.get("track_id") for t in tracks if t.get("track_id")]
    if not ids:
        return {}  # no ids -> nothing to look up (avoids an empty `IN ()`)

    conn, driver = get_db_connection(readonly=True)
    if not conn:
        return None
    placeholder = dialect_for(driver).placeholder
    cursor = conn.cursor()
    cursor.execute(
        f"""SELECT track_id, MAX(artist_name), MAX(duration_ms), COUNT(*)
            FROM listening_history WHERE track_id IN ({",".join([placeholder] * len(ids))})
            GROUP BY track_id""",
        ids,
    )
    known = {
        row[0]: {"artist": row[1], "duration_ms": row[2], "plays": row[3]}
        for row in cursor.fetchall()
    }
    conn.close()

    unknown = [track_id for track_id in ids if track_id not in known]
    if unknown:
        known.update(spotify_track_info(unknown))
    return known
