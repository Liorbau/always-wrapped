"""Executes agent runs on background threads so the UI can stream their steps.

A run that was stopped while we were working must never have its result
overwritten — that check guards every write back into the registry.
"""

import threading

from agents.analyst import build_analyst
from agents.dj import build_dj, run_dj_turn
from agents.evaluator import run_evaluator
from agents.llm import get_client
from app.modules.agent_api import events, proposals, runs
from core.logging import configure_logger

logger = configure_logger(__name__)

ANALYST_MAX_STEPS = 8

NO_PLAYLIST_RESPONSE = (
    "I couldn't build a playlist that meets all constraints — try relaxing the request."
)


def harness_for(session, kind):
    if session[kind] is None:
        llm = get_client(provider=session["provider"])
        session[kind] = build_dj(llm=llm) if kind == "dj" else build_analyst(llm=llm)
        session[kind].event_hook = _event_hook(kind)
    return session[kind]


def _event_hook(kind):
    return lambda text: events.record(kind, text)


def spawn(run_id, harness, kind, message):
    events.record(kind, "run started")
    threading.Thread(
        target=_execute, args=(run_id, harness, kind, message), daemon=True
    ).start()
    return run_id


def _execute(run_id, harness, kind, message):
    run = runs.RUNS[run_id]
    try:
        outcome = _dj_turn(harness, message) if kind == "dj" else _analyst_turn(harness, message)
        if not run["done"]:
            run["result"] = outcome
    except Exception as exc:
        logger.error("Agent run %s failed: %s", run_id, exc)
        run["error"] = "Agent error — check server logs."
    finally:
        run["done"] = True
        result_type = (run.get("result") or {}).get("type", "error")
        events.record(
            kind,
            f"run finished: {result_type} (${harness.metadata.get('cost_usd', 0):.3f})",
        )
        runs.release(run_id)


def _dj_turn(harness, message):
    outcome = run_dj_turn(harness, message)
    if not outcome["playlist"]:
        return {
            "type": "answer",
            "response": outcome["response"] or NO_PLAYLIST_RESPONSE,
            "withheld": bool(outcome["violations"]),
        }

    response = outcome["response"]
    if outcome.get("note"):
        response = f"{response}\n\n{outcome['note']}"
    return {
        "type": "playlist_proposal",
        "proposal_id": proposals.register(outcome["playlist"]),
        "playlist": outcome["playlist"],
        "response": response,
    }


def _analyst_turn(harness, message):
    return {"type": "answer", "response": harness.run(message, max_steps=ANALYST_MAX_STEPS)}


def spawn_evaluator(run_id, harness):
    events.record("evaluator", "learning pass started")
    threading.Thread(target=_execute_evaluator, args=(run_id, harness), daemon=True).start()
    return run_id


def _execute_evaluator(run_id, harness):
    run = runs.RUNS[run_id]
    try:
        outcome = run_evaluator(harness=harness)
        run["result"] = {"type": "answer", "response": outcome["report"]}
        for bias in outcome.get("biases", []):
            events.record(
                "evaluator",
                f"new preference: {bias['kind']} “{bias['key']}” {bias['delta']:+.2f}",
            )
        events.record(
            "evaluator",
            f"learned {outcome['applied']} preference(s) (${outcome['cost_usd']:.3f})",
        )
    except Exception as exc:
        logger.error("Evaluator run failed: %s", exc)
        run["error"] = "Evaluator error — check server logs."
    finally:
        run["done"] = True
        runs.release(run_id)
