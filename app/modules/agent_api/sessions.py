"""Per-conversation agent state.

In-memory on purpose: single user, and a restart just means re-asking.
"""

import os
import time

SESSION_TTL_S = 1800

SESSIONS = {}


def get_or_create(session_id, provider=None):
    """Switching provider starts a fresh session — a conversation cannot change
    models mid-context."""
    now = time.time()
    _evict_expired(now)

    session = SESSIONS.get(session_id)
    if session is None or (provider and provider != session["provider"]):
        session = {
            "dj": None,
            "analyst": None,
            "last_exchange": None,
            "provider": provider or os.getenv("LLM_PROVIDER", "openai"),
            "last_used": now,
        }
        SESSIONS[session_id] = session

    session["last_used"] = now
    return session


def _evict_expired(now):
    expired = [k for k, s in SESSIONS.items() if now - s["last_used"] > SESSION_TTL_S]
    for key in expired:
        del SESSIONS[key]


def clear():
    SESSIONS.clear()
