"""Pending playlist proposals and the one code path that writes to Spotify.

Nothing here runs without a human decision: `push` is only ever reached from an
Approve, and every outcome is appended to an audit log the Evaluator learns from.

Proposals are durable (DB) with a 24h TTL, single-use status, and restore-on
Spotify-failure so a retry is explicit and safe.
"""

from agents.store import pending_proposals as store
from integrations.spotify import push_playlist
from agents.store import hitl
from app.errors import not_found, upstream_error
from app.modules.agent_api import events
from core.logging import configure_logger

logger = configure_logger(__name__)


def register(playlist, proposal_id=None):
    return store.insert(playlist, proposal_id=proposal_id)


def take(proposal_id, *, to_status=store.APPROVED):
    playlist = store.claim(proposal_id, to_status)
    if playlist is None:
        raise not_found("Unknown, expired, or already-handled proposal.")
    return playlist


def push(proposal_id):
    """The HITL gate. Failure restores pending so the user can retry."""
    playlist = take(proposal_id, to_status=store.APPROVED)
    result = push_playlist(playlist)
    if "error" in result:
        store.restore_pending(proposal_id)
        raise upstream_error(result["error"])

    hitl.record_push(playlist, result.get("url"))
    events.record("spotify", f"playlist pushed: {playlist.get('name', '?')}")
    logger.info("Proposal %s approved and pushed.", proposal_id)
    return result


def reject(proposal_id, reason=None):
    playlist = take(proposal_id, to_status=store.REJECTED)
    record_rejection(playlist, reason)
    logger.info("Proposal %s rejected (reason=%r).", proposal_id, reason)
    return playlist


def discard(proposal_id, reason=None):
    """Tolerant reject for Telegram, where a double-tap must not raise."""
    playlist = store.claim(proposal_id, store.REJECTED)
    if playlist is not None:
        record_rejection(playlist, reason)
    return playlist


def record_rejection(playlist, reason):
    """Explicit negative signal for the Evaluator's next learning pass."""
    hitl.record_rejection(playlist, reason)


def clear():
    store.clear()


def is_pending(proposal_id):
    return store.is_pending(proposal_id)


class _PendingView(dict):
    """Test-facing mapping of still-pending id -> playlist (reads the DB)."""

    def values(self):
        return store.pending_playlists().values()

    def __contains__(self, key):
        return store.is_pending(key)

    def __getitem__(self, key):
        return store.pending_playlists()[key]

    def __setitem__(self, key, value):
        store.delete(key)
        store.insert(value, proposal_id=key)

    def clear(self):
        store.clear()


# Back-compat for tests that poked the old in-memory dict.
PENDING = _PendingView()
