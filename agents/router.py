"""Chat router: one cheap classification call before any agent runs.

The hard scope gate — off-topic messages never reach an agent at all, so the
product can't be talked into being a general-purpose chatbot. Set ROUTER_MODEL
to use a cheaper model for this (e.g. gpt-4o-mini); defaults to the session model.
"""

import os

from agents.harness import parse_final  # tolerant JSON extraction
from agents.llm import get_client
from core.logging import configure_logger

logger = configure_logger(__name__)

ROUTES = ("playlist_request", "data_question", "wrapped_request", "plan_day", "off_topic")

ROUTER_PROMPT = """You route messages for a Spotify listening-history companion app.
Classify the user's message into exactly one route:

- "playlist_request": they want a playlist built, modified, or pushed
- "data_question": a question about their listening data, stats, habits,
  artists, songs, genres, or anything music-related
- "wrapped_request": they want to see their Wrapped / recap / summary story
  ("show my weekly wrapped", "monthly recap", "fresh look for my wrapped")
- "plan_day": they want playlists planned for their day/tomorrow FROM THEIR
  CALENDAR ("plan my day", "plan tomorrow", "make playlists for my day",
  "soundtrack my schedule"). Distinct from playlist_request, which is a single
  ad-hoc playlist with no calendar involved.
- "off_topic": anything else (recipes, code, general knowledge, chit-chat
  unrelated to music)

Follow-ups: messages that are incomplete on their own ("how?", "why not?",
"more", "make it longer") continue the previous exchange — classify them into
the SAME route as that exchange, never off_topic. But a SELF-CONTAINED request
is classified on its own merits regardless of context: "give me a cake recipe"
right after a playlist exchange is still off_topic.
Arithmetic, coding, general knowledge and anything not about THIS user's music
are ALWAYS off_topic, even mid-conversation: "how much is 4*16?" -> off_topic.

Reply with JSON only: {"route": "<one of the routes above>", "satisfied": true}
"""


def router_client():
    model = os.getenv("ROUTER_MODEL")
    if not model and os.getenv("LLM_PROVIDER", "openai").lower() == "openai":
        model = "gpt-4o-mini"  # classification is trivial; 16x cheaper than 4o
    return get_client(model)


def route_message(message, llm=None, context=None):
    """Classify a chat message; falls back to data_question (read-only, cheap).

    context: (previous_user_message, previous_route) so follow-ups like
    "how for example?" stay in the conversation's domain.
    """
    llm = llm or router_client()
    content = message
    if context:
        prev_msg, prev_route = context
        content = (f"Previous user message: {prev_msg!r} (routed: {prev_route})\n"
                   f"Current message: {message!r}")
    try:
        resp = llm.complete(
            system=ROUTER_PROMPT,
            messages=[{"role": "user", "content": content}],
        )
        parsed = parse_final(resp["content"])
        r = parsed.get("route", "")
    except Exception as exc:
        logger.warning("Router failed (%s) — defaulting to data_question", exc)
        r = ""
    if r not in ROUTES:
        r = "data_question"
    logger.info("route=%s for message %r", r, message[:80])
    return r
