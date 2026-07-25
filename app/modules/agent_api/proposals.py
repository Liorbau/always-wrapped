"""Pending playlist proposals and the one code path that writes to Spotify.

Nothing here runs without a human decision: `push` is only ever reached from an
Approve, and every outcome is appended to an audit log the Evaluator learns from.
"""

import uuid

from integrations.spotify import push_playlist
from agents.store import hitl
from app.errors import not_found, upstream_error
from app.modules.agent_api import events
from core.logging import configure_logger

logger = configure_logger(__name__)

PENDING = {}


def register(playlist, proposal_id=None):
    proposal_id = proposal_id or uuid.uuid4().hex
    PENDING[proposal_id] = playlist
    return proposal_id


def take(proposal_id):
    playlist = PENDING.pop(proposal_id, None)
    if playlist is None:
        raise not_found("Unknown or already-handled proposal.")
    return playlist


def push(proposal_id):
    """The HITL gate. Failure puts the proposal back so the user can retry."""
    playlist = take(proposal_id)
    result = push_playlist(playlist)
    if "error" in result:
        PENDING[proposal_id] = playlist
        raise upstream_error(result["error"])

    hitl.record_push(playlist, result.get("url"))
    events.record("spotify", f"playlist pushed: {playlist.get('name', '?')}")
    logger.info("Proposal %s approved and pushed.", proposal_id)
    return result


def reject(proposal_id, reason=None):
    playlist = take(proposal_id)
    record_rejection(playlist, reason)
    logger.info("Proposal %s rejected (reason=%r).", proposal_id, reason)
    return playlist


def discard(proposal_id, reason=None):
    """Tolerant reject for Telegram, where a double-tap must not raise."""
    playlist = PENDING.pop(proposal_id, None)
    if playlist is not None:
        record_rejection(playlist, reason)
    return playlist


def record_rejection(playlist, reason):
    """Explicit negative signal for the Evaluator's next learning pass."""
    hitl.record_rejection(playlist, reason)


def clear():
    PENDING.clear()
