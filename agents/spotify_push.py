"""HITL-gated Spotify write: create a private playlist from an APPROVED proposal.

Deliberately NOT an agent tool — no agent can call this. Only the /api/agent/
approve endpoint invokes it, after a human clicked Approve on a proposal that
already passed the deterministic verifier.

Least privilege: this module uses its own OAuth token (.cache-push) with the
playlist-modify-private scope. The collector's token (.cache) stays read-only,
so the always-on deployed service can never write to the account.
The write is reversible: a private playlist the user can delete in one tap.
"""

import base64
import os

import spotipy
from spotipy.oauth2 import SpotifyOAuth
from dotenv import load_dotenv

from logging_config import configure_logger

load_dotenv()
logger = configure_logger(__name__)

PUSH_SCOPE = "playlist-modify-private ugc-image-upload"
PUSH_CACHE = ".cache-push"
COVER_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                          "static", "playlist_cover.jpg")


def get_push_client():
    """Authenticated client with write scope (separate token from the collector).

    Headless hosts (Render) can't do the browser consent — they recreate the
    token file from SPOTIFY_PUSH_CACHE_CONTENT, same pattern as the collector.
    """
    cache_content = os.getenv("SPOTIFY_PUSH_CACHE_CONTENT")
    if cache_content and not os.path.exists(PUSH_CACHE):
        try:
            with open(PUSH_CACHE, "w") as f:
                f.write(cache_content)
        except Exception as exc:
            logger.error("Failed to write %s: %s", PUSH_CACHE, exc)
    try:
        return spotipy.Spotify(
            auth_manager=SpotifyOAuth(
                client_id=os.getenv("SPOTIFY_CLIENT_ID"),
                client_secret=os.getenv("SPOTIFY_CLIENT_SECRET"),
                redirect_uri=os.getenv("SPOTIFY_REDIRECT_URI"),
                scope=PUSH_SCOPE,
                cache_path=PUSH_CACHE,
                open_browser=True,
            )
        )
    except Exception as exc:
        logger.error("Push client auth failed: %s", exc)
        return None


def push_playlist(playlist, sp=None):
    """Create the private playlist on the user's account. Returns {url, playlist_id}.

    Callers must pass only verifier-approved, human-approved proposals.
    """
    tracks = (playlist or {}).get("tracks") or []
    ids = [t.get("track_id") for t in tracks if t.get("track_id")]
    if not ids:
        return {"error": "No track ids to push."}

    sp = sp or get_push_client()
    if not sp:
        return {"error": "Spotify push client unavailable."}
    try:
        user_id = sp.current_user()["id"]
        created = sp.user_playlist_create(
            user_id,
            playlist.get("name") or "Always-Wrapped DJ",
            public=False,
            description=(playlist.get("description") or "")[:250]
            + " — built by the Always-Wrapped DJ, approved by you.",
        )
        sp.playlist_add_items(created["id"], ids)
    except Exception as exc:
        logger.error("Playlist push failed: %s", exc)
        return {"error": f"{type(exc).__name__}: {exc}"}

    try:  # brand cover — best-effort, a cover hiccup never fails the push
        with open(COVER_PATH, "rb") as f:
            sp.playlist_upload_cover_image(created["id"], base64.b64encode(f.read()))
    except Exception as exc:
        logger.warning("Cover upload skipped: %s", exc)

    url = (created.get("external_urls") or {}).get("spotify")
    logger.info("Pushed playlist %r (%d tracks): %s", playlist.get("name"), len(ids), url)
    return {"playlist_id": created["id"], "url": url, "track_count": len(ids)}
