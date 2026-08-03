"""Transport for the agent endpoints — parse, delegate, serialize.

Statuses: a started background run is 202; everything else is 200 or an
AppError mapped by the app-wide handler.
"""

from flask import Blueprint, jsonify, request

from app.errors import validation_error
from app.owner_auth import require_owner
from app.modules.agent_api.orchestrators import (
    approve_proposal,
    get_activity,
    get_plan_proposals,
    get_run_status,
    handle_telegram_update,
    list_commands,
    planner_schedule,
    reject_proposal,
    send_chat,
    start_planning,
    stop_run,
    trigger_evaluator,
)

agents_bp = Blueprint("agents_api", __name__, url_prefix="/api/agent")

TELEGRAM_SECRET_HEADER = "X-Telegram-Bot-Api-Secret-Token"


def _accepted(payload):
    return jsonify(payload), 202 if payload.get("type") == "run_started" else 200


@agents_bp.post("/chat")
@require_owner
def chat():
    body = request.get_json(silent=True) or {}
    return _accepted(send_chat.execute(
        body.get("message"),
        session_id=body.get("session_id"),
        provider=body.get("provider"),
    ))


@agents_bp.post("/evaluate")
@require_owner
def evaluate():
    return _accepted(trigger_evaluator.execute())


@agents_bp.get("/activity")
def activity():
    return jsonify(get_activity.execute())


@agents_bp.get("/commands")
def commands():
    """Public command dictionary for the chat “?” panel (no secrets)."""
    surface = (request.args.get("surface") or "web").lower()
    return jsonify(list_commands.for_surface(surface))


@agents_bp.get("/run/<run_id>")
def run_status(run_id):
    return jsonify(get_run_status.execute(run_id))


@agents_bp.post("/run/<run_id>/stop")
@require_owner
def run_stop(run_id):
    return jsonify(stop_run.execute(run_id))


@agents_bp.post("/approve")
@require_owner
def approve():
    body = request.get_json(silent=True) or {}
    return jsonify(approve_proposal.execute(body.get("proposal_id")))


@agents_bp.post("/reject")
@require_owner
def reject():
    body = request.get_json(silent=True) or {}
    return jsonify(reject_proposal.execute(body.get("proposal_id"), body.get("reason")))


@agents_bp.post("/plan")
@require_owner
def plan():
    return jsonify(start_planning.execute()), 202


@agents_bp.get("/plan/proposals")
@require_owner
def plan_proposals():
    return jsonify(get_plan_proposals.execute())


@agents_bp.get("/planner-time")
@require_owner
def get_planner_time():
    return jsonify(planner_schedule.current())


@agents_bp.put("/planner-time")
@require_owner
def put_planner_time():
    body = request.get_json(silent=True) or {}
    if "at" not in body:
        raise validation_error("Missing at (HH:MM or null/off).")
    return jsonify(planner_schedule.apply(body.get("at")))


@agents_bp.post("/telegram/webhook")
def telegram_webhook():
    return jsonify(handle_telegram_update.execute(
        request.headers.get(TELEGRAM_SECRET_HEADER, ""),
        request.get_json(silent=True) or {},
    ))
