"""One-time interactive consent for the playlist-push token.

Run this once after cloning (opens a browser); afterwards Approve pushes work
instantly with no login. For deployed hosts, copy the resulting .runtime/spotify-push.cache
content into a SPOTIFY_PUSH_CACHE_CONTENT env var.

    ./venv/bin/python scripts/authorize_push.py
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from integrations.spotify.push_client import get_push_client, PUSH_CACHE


def main():
    sp = get_push_client()
    if not sp:
        print("Push client could not be created — check .env Spotify keys.")
        sys.exit(1)
    user = sp.current_user()  # forces the OAuth flow if no cached token
    print(f"Push token authorized for {user['display_name']!r} -> {PUSH_CACHE}")
    print("Deployed host? Copy the file's content into SPOTIFY_PUSH_CACHE_CONTENT.")


if __name__ == "__main__":
    main()
