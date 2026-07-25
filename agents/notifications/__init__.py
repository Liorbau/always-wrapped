"""Notifier selection.

    NOTIFIER=telegram   (default)
    NOTIFIER=none       in-app approval only

Adding a channel means adding one module here and one registry entry; no
caller changes.
"""

import os

from agents.notifications.null import NullNotifier
from agents.notifications.telegram import TelegramNotifier
from core.logging import configure_logger

logger = configure_logger(__name__)

NOTIFIERS = {
    "telegram": TelegramNotifier,
    "none": NullNotifier,
}
DEFAULT_NOTIFIER = "telegram"

_current = None


def get_notifier():
    global _current
    if _current is None:
        _current = _build()
    return _current


def set_notifier(notifier):
    """Explicit override for tests and for wiring a channel by hand."""
    global _current
    _current = notifier
    return notifier


def reset_notifier():
    global _current
    _current = None


def _build():
    choice = os.getenv("NOTIFIER", DEFAULT_NOTIFIER).lower()
    if choice not in NOTIFIERS:
        raise ValueError(
            f"Unknown NOTIFIER {choice!r}; expected one of {sorted(NOTIFIERS)}"
        )
    notifier = NOTIFIERS[choice]()
    if not notifier.enabled():
        logger.warning("Notifier %r is selected but not configured — "
                       "proposals will be in-app only.", choice)
    return notifier
