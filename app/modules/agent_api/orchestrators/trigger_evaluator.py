"""Runs the Evaluator in-process so the observatory shows it working live.
Same learning pass as scripts/run_evaluator.py, same single-flight guard."""

from agents.evaluator import build_evaluator
from agents.ledger import budget_left
from app.errors import budget_exhausted
from app.modules.agent_api import events, runner, runs


def execute():
    if budget_left() <= 0:
        raise budget_exhausted("Daily agent budget reached.")

    with runs.lock:
        runs.claim_slot()
        harness = build_evaluator()
        harness.event_hook = lambda text: events.record("evaluator", text)
        run_id = runs.register(harness, "evaluator")

    runner.spawn_evaluator(run_id, harness)
    return {"type": "run_started", "run_id": run_id}
