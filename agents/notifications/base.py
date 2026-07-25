"""The notification seam, named by role rather than vendor.

An implementation's job is to reach the human for approval and to keep the
card it sent up to date. Nothing above this layer knows what a chat_id or a
message_id is — a card reference is opaque and only the implementation that
produced it can read it.
"""

from typing import Any, Dict, Optional, Protocol, runtime_checkable

CardRef = Optional[Dict[str, Any]]


@runtime_checkable
class Notifier(Protocol):
    name: str

    def enabled(self) -> bool:
        """False when the channel is not configured; callers may skip it."""

    def send_proposal(self, block, playlist, proposal_id, recipient=None) -> CardRef:
        """Ask the human to approve a playlist. Returns an opaque card
        reference for later updates, or None when nothing was sent."""

    def send_message(self, recipient, text) -> bool:
        """Plain text (timer replies, failure notices)."""

    def acknowledge(self, interaction_id, text="") -> bool:
        """Confirm receipt of a tap, where the channel supports it."""

    def update_card(self, card_ref, text) -> bool:
        """Replace the body of a previously sent proposal card."""
