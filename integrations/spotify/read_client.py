"""Read-only Spotify client: recently-played history and catalog lookups.

This is the token the always-on service runs on. It cannot modify the account —
writing needs push_client and a human Approve.
"""

import os

import spotipy
from dotenv import load_dotenv
from spotipy.exceptions import SpotifyException
from spotipy.oauth2 import SpotifyOAuth

from core.logging import configure_logger
from core.paths import SPOTIFY_READ_CACHE, ensure_parent

logger = configure_logger(__name__)

load_dotenv()
SCOPE = "user-read-recently-played"


def auth_connection():
    """Authenticate with Spotify and return the client, or None on failure."""
    logger.info("Attempting to connect to Spotify...")
    _restore_cache_from_env()

    try:
        client = spotipy.Spotify(
            auth_manager=SpotifyOAuth(
                client_id=os.getenv("SPOTIFY_CLIENT_ID"),
                client_secret=os.getenv("SPOTIFY_CLIENT_SECRET"),
                redirect_uri=os.getenv("SPOTIFY_REDIRECT_URI"),
                scope=SCOPE,
                cache_path=SPOTIFY_READ_CACHE,
                open_browser=True,
            )
        )
        logger.info("Spotify client created successfully.")
        return client
    except (SpotifyException, OSError) as exc:
        logger.exception("Authentication failed: %s", exc)
        return None


def _restore_cache_from_env():
    """Headless hosts can't do browser consent — they ship the token as env."""
    cache_content = os.getenv("SPOTIFY_CACHE_CONTENT")
    if not cache_content or os.path.exists(SPOTIFY_READ_CACHE):
        return
    logger.info("Recreating the Spotify read token cache from the environment.")
    try:
        with open(ensure_parent(SPOTIFY_READ_CACHE), "w") as handle:
            handle.write(cache_content)
    except OSError as exc:
        logger.error("Failed to write %s: %s", SPOTIFY_READ_CACHE, exc)


if __name__ == "__main__":
    # Run directly to (re)mint the OAuth token: opens the browser, then writes a
    # fresh cache. The recently-played call forces the token exchange so the
    # cache is actually populated before we exit.
    sp = auth_connection()
    if sp:
        sp.current_user_recently_played(limit=1)
        logger.info("Spotify authenticated — fresh token cache written.")
    else:
        logger.error("Spotify authentication failed — no token cache written.")
