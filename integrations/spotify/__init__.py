"""Spotify OAuth adapters, deliberately split by scope.

    read_client   user-read-recently-played          — used by the always-on service
    push_client   playlist-modify-private + cover    — used only after a human Approve

Two separate tokens, two separate cache files. The collector and every agent
hold the read token, so no headless code path can write to the account even if
it wanted to.
"""

from integrations.spotify.push_client import get_push_client, push_playlist
from integrations.spotify.read_client import auth_connection

__all__ = ["auth_connection", "get_push_client", "push_playlist"]
