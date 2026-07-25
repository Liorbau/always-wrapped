"""Every path the app writes to at runtime, declared in one place.

These are deliberately grouped under a single directory so a host can mount one
volume (or accept that one directory is ephemeral) and know exactly what it is
holding. Override the root with RUNTIME_DIR.

Nothing here is source: the OAuth token caches are regenerable, and everything
else the agents produce (run costs, approve/reject history) goes to the
database instead of disk.
"""

import os

RUNTIME_DIR = os.getenv("RUNTIME_DIR", ".runtime")

SPOTIFY_READ_CACHE = os.path.join(RUNTIME_DIR, "spotify-read.cache")
SPOTIFY_PUSH_CACHE = os.path.join(RUNTIME_DIR, "spotify-push.cache")


def ensure_parent(path):
    """Create the directory a file is about to be written into."""
    parent = os.path.dirname(path)
    if parent:
        os.makedirs(parent, exist_ok=True)
    return path
