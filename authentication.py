"""Simple helper to perform Spotify authentication and
fetch data for the authenticated user.

This module is intended to be run as a script for quick auth
verification.
"""

import os

import spotipy
from spotipy.oauth2 import SpotifyOAuth
from spotipy.exceptions import SpotifyException
from dotenv import load_dotenv

from logging_config import configure_logger

logger = configure_logger(__name__)

load_dotenv()
SCOPE = "user-read-recently-played"


def auth_connection():
    """Authenticates with Spotify and returns the client object (sp)."""

    logger.info("Attempting to connect to Spotify...")

    cache_content = os.getenv("SPOTIFY_CACHE_CONTENT")
    if cache_content and not os.path.exists(".cache"):
        logger.info("Recreating .cache file from Environment Variable...")
        try:
            with open(".cache", "w") as f:
                f.write(cache_content)
        except Exception as eec:
            logger.error("Failed to write .cache file: %s", exc)

    try:
        sp = spotipy.Spotify(
            auth_manager=SpotifyOAuth(
                client_id=os.getenv("SPOTIFY_CLIENT_ID"),
                client_secret=os.getenv("SPOTIFY_CLIENT_SECRET"),
                redirect_uri=os.getenv("SPOTIFY_REDIRECT_URI"),
                scope=SCOPE,
                open_browser=True,
            )
        )

        logger.info("Spotify client created successfully.")
        return sp

    except (SpotifyException, OSError) as exc:
        logger.exception("Authentication failed: %s", exc)
        return None
