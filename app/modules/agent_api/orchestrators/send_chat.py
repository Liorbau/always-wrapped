"""Chat entry point: budget gate, route, then refuse / redirect / start a run."""

import uuid

from agents.ledger import budget_left
from agents.llm import PROVIDERS
from agents.router import route_message
from app.errors import budget_exhausted, validation_error
from app.modules.agent_api import events, planning, runner, runs, sessions, wrap_spec

REFUSAL_TEXT = (
    "I'm your music companion — I can build playlists and answer questions "
    "about your listening history. I can't help with that."
)
CHAT_OVER_BUDGET = "Daily agent budget reached — the DJ is off until tomorrow."
PLAN_OVER_BUDGET = "Daily agent budget reached — planning is off until tomorrow."
PLANNING_STARTED = (
    "Planning tomorrow from your calendar — I'll send each playlist to your "
    "Telegram to approve."
)
PLANNING_BUSY = "Already planning your day — the proposals will land in your Telegram."


def execute(message, session_id=None, provider=None):
    message = (message or "").strip()
    if not message:
        raise validation_error("Empty message.")

    provider = (provider or "").lower() or None
    if provider and provider not in PROVIDERS:
        raise validation_error(f"Unknown provider {provider!r}.", {"provider": provider})
    if budget_left() <= 0:
        raise budget_exhausted(CHAT_OVER_BUDGET)

    with runs.lock:
        runs.claim_slot()
        session_id = session_id or uuid.uuid4().hex[:12]
        session = sessions.get_or_create(session_id, provider)

        route = route_message(message, context=session.get("last_exchange"))
        events.record("router", f"“{message[:48]}” → {route}")
        if route == "off_topic":
            return {"type": "refusal", "response": REFUSAL_TEXT}
        session["last_exchange"] = (message[:200], route)

        if route == "wrapped_request":
            return _wrapped_redirect(message)
        if route == "plan_day":
            return _planning_redirect()

        kind = "dj" if route == "playlist_request" else "analyst"
        harness = runner.harness_for(session, kind)
        run_id = runs.register(harness, kind)

    runner.spawn(run_id, harness, kind, message)
    return {"type": "run_started", "run_id": run_id, "route": route, "session_id": session_id}


def _wrapped_redirect(message):
    spec = wrap_spec.extract(message)
    events.record("wrapped", f"building {spec['period']} edition")
    return {"type": "wrapped", "response": "Rolling your Wrapped…", **spec}


def _planning_redirect():
    started, reason = planning.start()
    events.record("planner", "plan-my-day requested from chat")
    if not started and reason == "budget":
        raise budget_exhausted(PLAN_OVER_BUDGET)
    return {"type": "planning", "response": PLANNING_STARTED if started else PLANNING_BUSY}
