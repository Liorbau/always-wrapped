"""Parses the recap period out of a chat message ('june', 'last month', dates).

One cheap model call with a keyword fallback, so a parse failure degrades to a
sensible edition instead of an error.
"""

import time

from agents.harness import parse_final
from agents.router import router_client
from core.logging import configure_logger

logger = configure_logger(__name__)

FRESH_WORDS = ("fresh", "new look", "regenerate")


def _system_prompt():
    return (
        "Parse a request for a listening-recap period. Today (UTC) is "
        + time.strftime("%Y-%m-%d") + ". Reply JSON only: "
        '{"period": "week"|"month"|"custom", "start": "YYYY-MM-DD"|null, '
        '"end": "YYYY-MM-DD"|null, "fresh": true|false, "satisfied": true}. '
        "week = current week, month = current calendar month; any other "
        "range (a named month, 'last week', explicit dates) = custom with "
        "start/end filled (inclusive). fresh = they want a regenerated look."
    )


def extract(message):
    try:
        response = router_client().complete(
            system=_system_prompt(),
            messages=[{"role": "user", "content": message}],
        )
        parsed = parse_final(response["content"])
        period, start, end = parsed.get("period"), parsed.get("start"), parsed.get("end")
        force = bool(parsed.get("fresh"))
        if period == "custom" and start and end:
            return {"period": "custom", "start": start, "end": end, "force": force}
        if period in ("week", "month"):
            return {"period": period, "start": None, "end": None, "force": force}
    except Exception as exc:
        logger.warning("Wrap spec extraction failed, falling back: %s", exc)

    return _keyword_fallback(message)


def _keyword_fallback(message):
    lowered = message.lower()
    return {
        "period": "month" if "month" in lowered else "week",
        "start": None,
        "end": None,
        "force": any(word in lowered for word in FRESH_WORDS),
    }
