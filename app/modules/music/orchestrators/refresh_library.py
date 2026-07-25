"""Manual Spotify sync. The cooldown guards the shared quota on the public
demo — one sync only ever covers the last 50 plays anyway."""

import time

from app.errors import upstream_error
from integrations.spotify import auth_connection
from pipelines.collector import fetch_recent_tracks, save_tracks_to_db

COOLDOWN_S = 60

_last_sync = {"ts": 0.0}


def execute():
    if time.time() - _last_sync["ts"] < COOLDOWN_S:
        return {"status": "success", "count": 0, "note": "Synced less than a minute ago."}

    sp = auth_connection()
    if sp is None:
        raise upstream_error("Couldn't connect to Spotify.")

    tracks = fetch_recent_tracks(sp)
    save_tracks_to_db(tracks, sp)
    _last_sync["ts"] = time.time()
    return {"status": "success", "count": len(tracks)}
