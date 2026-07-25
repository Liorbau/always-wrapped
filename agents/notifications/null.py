"""No outbound channel.

Chosen with NOTIFIER=none. Proposals still appear in the in-app chat and are
still approved there — this only silences the push channel, it never changes
what the agents are allowed to do.
"""

from core.logging import configure_logger

logger = configure_logger(__name__)


class NullNotifier:
    name = "none"

    def enabled(self):
        return False

    def send_proposal(self, block, playlist, proposal_id, recipient=None):
        logger.info("Notifications disabled; proposal %s is in-app only.", proposal_id)
        return None

    def send_message(self, recipient, text):
        return False

    def acknowledge(self, interaction_id, text=""):
        return False

    def update_card(self, card_ref, text):
        return False
