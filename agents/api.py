"""Flask blueprint for the v2 agent endpoints.

Chat flow (async, so the UI can stream the agent's steps live):
  POST /api/agent/chat    -> budget gate -> router -> refusal, or start a
                             background run; returns {run_id} immediately
  GET  /api/agent/run/<id> -> live step feed from the harness trajectory +
                             the final result when done
  POST /api/agent/approve  -> the ONLY account-write path (HITL)
  POST /api/agent/reject   -> discard; optional reason logged for the Evaluator

Multi-turn: a session keeps one live harness per persona, so "swap the
Radiohead track" continues the same DJ conversation. Switching provider
starts a fresh session (a conversation can't change models mid-context).
State is in-memory: single user; a restart just means re-asking.
"""

import hmac
import json
import os
import threading
import time
import uuid
import itertools
from collections import deque

from flask import Blueprint, jsonify, request

from agents.analyst import build_analyst
from agents.dj import build_dj, run_dj_turn
from agents.evaluator import build_evaluator, run_evaluator
from agents.planner import plan_tomorrow
from agents import telegram, timers
from agents.ledger import budget_left, daily_spent, DAILY_BUDGET_USD
from agents.llm import PROVIDERS, get_client
from agents.harness import _parse_final
from agents.router import route_message, _router_client
from agents.spotify_push import push_playlist
from logging_config import configure_logger

logger = configure_logger(__name__)

agents_bp = Blueprint("agents_api", __name__, url_prefix="/api/agent")

SESSION_TTL_S = 1800
ANALYST_MAX_STEPS = 8

EVENTS = deque(maxlen=80)  # live feed for the /agents observatory
_EVENT_ID = itertools.count(1)


def _event(node, text):
    EVENTS.append({"id": next(_EVENT_ID), "ts": time.strftime("%H:%M:%S"),
                   "node": node, "text": text[:120]})


MAX_RUNS = 40  # keep the run registry bounded on the long-lived server

SESSIONS = {}  # sid -> {"dj", "analyst", "provider", "last_used"}
RUNS = {}      # run_id -> {"harness", "kind", "done", "result", "error"}
PENDING_PROPOSALS = {}
PLAN_MSGS = {}          # proposal_id -> {chat_id, message_id} for Telegram edits
_planner_busy = {"on": False}
_run_lock = threading.Lock()
_active_run = {"id": None}

REFUSAL_TEXT = (
    "I'm your music companion — I can build playlists and answer questions "
    "about your listening history. I can't help with that."
)

REJECTIONS_LOG = os.path.join("agent-runs", "rejections.jsonl")
PUSHES_LOG = os.path.join("agent-runs", "pushes.jsonl")


def _evict_runs():
    """Drop the oldest finished runs so RUNS can't grow without bound."""
    while len(RUNS) > MAX_RUNS:
        for rid, r in list(RUNS.items()):
            if r["done"] and rid != _active_run["id"]:
                del RUNS[rid]
                break
        else:
            break


def _session(sid, provider):
    """Get/create the session; a provider change resets it (fresh context)."""
    now = time.time()
    for key in [k for k, s in SESSIONS.items() if now - s["last_used"] > SESSION_TTL_S]:
        del SESSIONS[key]
    s = SESSIONS.get(sid)
    if s is None or (provider and provider != s["provider"]):
        s = {"dj": None, "analyst": None, "last_exchange": None,
             "provider": provider or os.getenv("LLM_PROVIDER", "openai"), "last_used": now}
        SESSIONS[sid] = s
    s["last_used"] = now
    return s


def _extract_wrap_spec(message):
    """Mini-LLM parse of the requested period ('june', 'last month', 'first
    week of may', explicit dates...). Deterministic fallback: keywords."""
    try:
        resp = _router_client().complete(
            system=(
                "Parse a request for a listening-recap period. Today (UTC) is "
                + time.strftime("%Y-%m-%d") + ". Reply JSON only: "
                '{"period": "week"|"month"|"custom", "start": "YYYY-MM-DD"|null, '
                '"end": "YYYY-MM-DD"|null, "fresh": true|false, "satisfied": true}. '
                "week = current week, month = current calendar month; any other "
                "range (a named month, 'last week', explicit dates) = custom with "
                "start/end filled (inclusive). fresh = they want a regenerated look."
            ),
            messages=[{"role": "user", "content": message}],
        )
        parsed = _parse_final(resp["content"])
        period = parsed.get("period")
        start, end = parsed.get("start"), parsed.get("end")
        if period == "custom" and start and end:
            return {"period": "custom", "start": start, "end": end,
                    "force": bool(parsed.get("fresh"))}
        if period in ("week", "month"):
            return {"period": period, "start": None, "end": None,
                    "force": bool(parsed.get("fresh"))}
    except Exception as exc:
        logger.warning("wrap spec extraction failed: %s", exc)
    lower = message.lower()
    return {"period": "month" if "month" in lower else "week", "start": None,
            "end": None, "force": any(w in lower for w in ("fresh", "new look", "regenerate"))}


def _step_label(entry):
    """Terse, high-level activity phrase for the live status line."""
    if entry["type"] == "tool_call":
        return {
            "query_history": "exploring your history",
            "search_spotify": "searching Spotify",
            "artist_top_tracks": "collecting candidate tracks",
            "get_audio_features": "checking the mood",
            "discover_new_tracks": "hunting new music",
        }.get(entry["tool"], "working")
    if entry["type"] == "compaction":
        return "organizing thoughts"
    return "assembling the answer"


def _execute(run_id, harness, kind, message):
    run = RUNS[run_id]
    try:
        if kind == "dj":
            out = run_dj_turn(harness, message)
            if run["done"]:  # stopped while we were working — don't overwrite
                return
            if out["playlist"]:
                proposal_id = uuid.uuid4().hex[:12]
                PENDING_PROPOSALS[proposal_id] = out["playlist"]
                response = out["response"]
                if out.get("note"):
                    response = f"{response}\n\n{out['note']}"
                run["result"] = {"type": "playlist_proposal", "proposal_id": proposal_id,
                                 "playlist": out["playlist"], "response": response}
            else:
                run["result"] = {"type": "answer", "response": out["response"]
                                 or "I couldn't build a playlist that meets all constraints — "
                                    "try relaxing the request.",
                                 "withheld": bool(out["violations"])}
        else:
            response = harness.run(message, max_steps=ANALYST_MAX_STEPS)
            if run["done"]:
                return
            run["result"] = {"type": "answer", "response": response}
    except Exception as exc:
        logger.error("Agent run %s failed: %s", run_id, exc)
        run["error"] = "Agent error — check server logs."
    finally:
        run["done"] = True
        result_type = (run.get("result") or {}).get("type", "error")
        _event(kind, f"run finished: {result_type} "
                     f"(${harness.metadata.get('cost_usd', 0):.3f})")
        if _active_run["id"] == run_id:  # never clear a newer run's slot
            _active_run["id"] = None


@agents_bp.route("/chat", methods=["POST"])
def agent_chat():
    body = request.get_json(silent=True) or {}
    message = (body.get("message") or "").strip()
    if not message:
        return jsonify({"error": "Empty message."}), 400
    provider = (body.get("provider") or "").lower() or None
    if provider and provider not in PROVIDERS:
        return jsonify({"error": f"Unknown provider {provider!r}."}), 400
    if budget_left() <= 0:
        return jsonify({"type": "refusal",
                        "response": "Daily agent budget reached — the DJ is off until tomorrow."}), 429

    with _run_lock:
        active = _active_run["id"]
        if active and not RUNS[active]["done"]:
            if time.time() - RUNS[active].get("started", 0) > 300:
                RUNS[active]["harness"].cancelled = True  # wind the old thread down
                RUNS[active]["done"] = True   # stale run: stop blocking the user
                RUNS[active]["error"] = "Run timed out."
                _active_run["id"] = None
            else:
                return jsonify({"error": "An agent is already working — wait for it to finish."}), 409

        sid = body.get("session_id") or uuid.uuid4().hex[:12]
        session = _session(sid, provider)
        route = route_message(message, context=session.get("last_exchange"))
        _event("router", f"“{message[:48]}” → {route}")
        if route == "off_topic":
            return jsonify({"type": "refusal", "response": REFUSAL_TEXT})
        session["last_exchange"] = (message[:200], route)

        if route == "wrapped_request":
            spec = _extract_wrap_spec(message)
            _event("wrapped", f"building {spec['period']} edition")
            return jsonify({"type": "wrapped", "response": "Rolling your Wrapped…", **spec})
        kind = "dj" if route == "playlist_request" else "analyst"
        if session[kind] is None:
            llm = get_client(provider=session["provider"])
            session[kind] = build_dj(llm=llm) if kind == "dj" else build_analyst(llm=llm)
            session[kind].event_hook = (lambda k: lambda text: _event(k, text))(kind)
        harness = session[kind]

        run_id = uuid.uuid4().hex[:12]
        RUNS[run_id] = {"harness": harness, "kind": kind, "done": False,
                        "result": None, "error": None, "started": time.time()}
        _active_run["id"] = run_id
        _evict_runs()

    _event(kind, "run started")
    threading.Thread(target=_execute, args=(run_id, harness, kind, message), daemon=True).start()
    return jsonify({"run_id": run_id, "route": route, "session_id": sid}), 202


@agents_bp.route("/evaluate", methods=["POST"])
def trigger_evaluator():
    """Run the Evaluator in-process so the observatory shows it working live.
    Same learning pass as scripts/run_evaluator.py, same single-flight guard."""
    if budget_left() <= 0:
        return jsonify({"error": "Daily agent budget reached."}), 429
    with _run_lock:
        active = _active_run["id"]
        if active and not RUNS[active]["done"]:
            return jsonify({"error": "An agent is already working — wait for it to finish."}), 409
        harness = build_evaluator()
        harness.event_hook = lambda text: _event("evaluator", text)
        run_id = uuid.uuid4().hex[:12]
        RUNS[run_id] = {"harness": harness, "kind": "evaluator", "done": False,
                        "result": None, "error": None, "started": time.time()}
        _active_run["id"] = run_id

    def _run():
        run = RUNS[run_id]
        try:
            out = run_evaluator(harness=harness)
            run["result"] = {"type": "answer", "response": out["report"]}
            for b in out.get("biases", []):
                _event("evaluator",
                       f"new preference: {b['kind']} “{b['key']}” {b['delta']:+.2f}")
            _event("evaluator", f"learned {out['applied']} preference(s) "
                                f"(${out['cost_usd']:.3f})")
        except Exception as exc:
            logger.error("Evaluator run failed: %s", exc)
            run["error"] = "Evaluator error — check server logs."
        finally:
            run["done"] = True
            if _active_run["id"] == run_id:
                _active_run["id"] = None

    _event("evaluator", "learning pass started")
    threading.Thread(target=_run, daemon=True).start()
    return jsonify({"run_id": run_id}), 202


@agents_bp.route("/activity", methods=["GET"])
def activity():
    """Live state for the /agents observatory: active node, feed, spend."""
    active = None
    rid = _active_run["id"]
    if rid and rid in RUNS and not RUNS[rid]["done"]:
        run = RUNS[rid]
        traj = list(run["harness"].trajectory)
        active = {
            "agent": run["kind"],
            "doing": _step_label(traj[-1]) if traj else "thinking",
            "steps": len(traj),
            "cost": round(run["harness"].metadata.get("cost_usd", 0), 4),
        }
    return jsonify({
        "active": active,
        "events": list(EVENTS)[-40:],
        "daily_cost": round(daily_spent(), 4),
        "daily_budget": DAILY_BUDGET_USD,
    })


@agents_bp.route("/run/<run_id>", methods=["GET"])
def run_status(run_id):
    run = RUNS.get(run_id)
    if run is None:
        return jsonify({"error": "Unknown run."}), 404
    steps = [_step_label(e) for e in list(run["harness"].trajectory)]
    payload = {"done": run["done"], "steps": steps}
    if run["done"]:
        payload["result"] = run["result"]
        payload["error"] = run["error"]
    return jsonify(payload)


@agents_bp.route("/run/<run_id>/stop", methods=["POST"])
def run_stop(run_id):
    """Free the DJ mid-run: cooperative cancel + immediately unblock new chats."""
    run = RUNS.get(run_id)
    if run is None:
        return jsonify({"error": "Unknown run."}), 404
    if not run["done"]:
        run["harness"].cancelled = True
        run["done"] = True  # cancelled flag makes the background thread exit its loop
        run["result"] = {"type": "answer", "response": "Stopped. Ask me anything."}
        with _run_lock:
            if _active_run["id"] == run_id:
                _active_run["id"] = None
        logger.info("Run %s stopped by user.", run_id)
    return jsonify({"type": "stopped"})


def _push_pending(proposal_id):
    """Push an approved proposal (the ONLY account-write path). Returns
    (result, None) on success or (None, (payload, status)) on failure."""
    playlist = PENDING_PROPOSALS.pop(proposal_id, None)
    if playlist is None:
        return None, ({"error": "Unknown or already-handled proposal."}, 404)
    result = push_playlist(playlist)
    if "error" in result:
        PENDING_PROPOSALS[proposal_id] = playlist  # let the user retry
        return None, (result, 502)
    try:  # record for the Evaluator: what was pushed, when
        os.makedirs(os.path.dirname(PUSHES_LOG), exist_ok=True)
        with open(PUSHES_LOG, "a") as f:
            f.write(json.dumps({"ts": time.strftime("%Y-%m-%dT%H:%M:%S"),
                                "url": result.get("url"),
                                "playlist": playlist}) + "\n")
    except Exception as exc:
        logger.warning("Push log write failed: %s", exc)
    _event("spotify", f"playlist pushed: {playlist.get('name', '?')}")
    return result, None


@agents_bp.route("/approve", methods=["POST"])
def agent_approve():
    """The HITL gate: the ONLY code path that writes to the Spotify account."""
    proposal_id = (request.get_json(silent=True) or {}).get("proposal_id")
    result, err = _push_pending(proposal_id)
    if err:
        payload, status = err
        return jsonify(payload), status
    logger.info("Proposal %s approved and pushed.", proposal_id)
    return jsonify({"type": "pushed", **result})


@agents_bp.route("/reject", methods=["POST"])
def agent_reject():
    body = request.get_json(silent=True) or {}
    proposal_id = body.get("proposal_id")
    playlist = PENDING_PROPOSALS.pop(proposal_id, None)
    if playlist is None:
        return jsonify({"error": "Unknown or already-handled proposal."}), 404
    _record_rejection(playlist, body.get("reason"))
    _event("user", f"proposal rejected ({(body.get('reason') or 'no reason')[:40]})")
    logger.info("Proposal %s rejected (reason=%r).", proposal_id, body.get("reason"))
    return jsonify({"type": "rejected"})


def _record_rejection(playlist, reason):
    """Persist a rejected proposal as explicit negative signal for the Evaluator."""
    try:
        os.makedirs(os.path.dirname(REJECTIONS_LOG), exist_ok=True)
        with open(REJECTIONS_LOG, "a") as f:
            f.write(json.dumps({
                "ts": time.strftime("%Y-%m-%dT%H:%M:%S"),
                "reason": (reason or "").strip()[:500],
                "playlist": playlist,
            }) + "\n")
    except Exception as exc:
        logger.warning("Rejection log write failed: %s", exc)


def _run_planner():
    """Background: plan tomorrow, register each proposal, notify over Telegram."""
    try:
        _event("planner", "reading tomorrow's calendar")
        out = plan_tomorrow()
        if "error" in out:
            _event("planner", f"stopped: {out['error']}")
            return
        proposals = out.get("proposals", [])
        for p in proposals:
            proposal_id = uuid.uuid4().hex
            PENDING_PROPOSALS[proposal_id] = p["playlist"]
            block = p["block"]
            _event("planner", f"proposed '{p['playlist'].get('name','?')}' for {block['title']}")
            resp = telegram.send_proposal(block, p["playlist"], proposal_id)
            msg = (resp or {}).get("result") or {}
            if msg.get("message_id"):
                PLAN_MSGS[proposal_id] = {"chat_id": msg["chat"]["id"],
                                          "message_id": msg["message_id"]}
            elif "error" in (resp or {}):
                logger.warning("Telegram notify failed for %s: %s", proposal_id, resp["error"])
        _event("planner", f"done: {len(proposals)} playlist(s) awaiting approval")
        logger.info("Planner run: %d proposal(s), $%.4f.", len(proposals), out.get("cost_usd", 0))
    except Exception as exc:
        logger.exception("Planner run failed.")
        _event("planner", f"failed: {type(exc).__name__}")
    finally:
        _planner_busy["on"] = False


@agents_bp.route("/plan", methods=["POST"])
def trigger_planner():
    """Kick off the headless Planner (cron or the 'Plan my day' button)."""
    if budget_left() <= 0:
        return jsonify({"error": "Daily budget reached."}), 429
    if _planner_busy["on"]:
        return jsonify({"error": "A plan is already running."}), 409
    _planner_busy["on"] = True
    threading.Thread(target=_run_planner, daemon=True).start()
    return jsonify({"type": "planning"}), 202


def _fire_timer(row):
    """One timer firing: run the DJ on the saved prompt, propose over Telegram.
    Account-read-only — the push still waits for the Approve tap."""
    _event("timer", f"⏰ #{row['id']} fired: {row['prompt'][:60]}")
    if budget_left() <= 0:
        telegram.send_message(row["chat_id"], f"⏰ Timer #{row['id']} skipped — "
                              "daily agent budget reached.")
        return
    try:
        out = run_dj_turn(build_dj(), row["prompt"])
    except Exception:
        logger.exception("Timer %s DJ run failed.", row["id"])
        telegram.send_message(row["chat_id"], f"⏰ Timer #{row['id']} failed — "
                              "couldn't build the playlist this time.")
        return
    playlist = out.get("playlist")
    if not playlist:
        telegram.send_message(row["chat_id"], f"⏰ Timer #{row['id']}: no playlist "
                              f"this time. {(out.get('response') or '')[:200]}")
        return
    proposal_id = uuid.uuid4().hex
    PENDING_PROPOSALS[proposal_id] = playlist
    block = {"title": f"timer #{row['id']}", "start": row["at_hhmm"]}
    resp = telegram.send_proposal(block, playlist, proposal_id, chat_id=row["chat_id"])
    msg = (resp or {}).get("result") or {}
    if msg.get("message_id"):
        PLAN_MSGS[proposal_id] = {"chat_id": msg["chat"]["id"],
                                  "message_id": msg["message_id"]}
    _event("timer", f"proposed '{playlist.get('name', '?')}' awaiting approval")


def start_timer_thread():
    """Spawn the once-a-minute timer loop (called from server startup)."""
    threading.Thread(target=timers.start_timer_service,
                     args=(_fire_timer,), daemon=True).start()


@agents_bp.route("/telegram/webhook", methods=["POST"])
def telegram_webhook():
    """Handles Approve/Reject taps and /timer commands from Telegram. This is
    a WRITE TRIGGER, so the secret token is validated on every call before
    anything acts."""
    secret = os.getenv("TELEGRAM_WEBHOOK_SECRET", "")
    got = request.headers.get("X-Telegram-Bot-Api-Secret-Token", "")
    if not secret or not hmac.compare_digest(got, secret):
        logger.warning("Telegram webhook rejected: bad secret token.")
        return jsonify({"error": "forbidden"}), 403

    update = request.get_json(silent=True) or {}
    cq = update.get("callback_query")
    if not cq:
        # text message: only /commands, only from the owner's chat (fail closed)
        msg = update.get("message") or {}
        chat_id = str((msg.get("chat") or {}).get("id", ""))
        text = (msg.get("text") or "").strip()
        owner = os.getenv("TELEGRAM_CHAT_ID", "")
        if not text.startswith("/") or not owner or chat_id != owner:
            return jsonify({"type": "ignored"})
        try:
            reply = timers.handle_command(text, chat_id)
        except Exception:
            logger.exception("Timer command failed: %s", text[:80])
            reply = "Something broke handling that — try again."
        telegram.send_message(chat_id, reply)
        return jsonify({"type": "ok"})
    # Approve is THE account-write trigger — only the owner may tap it, even
    # though proposals are only sent to their chat (fail closed on writes).
    owner = os.getenv("TELEGRAM_CHAT_ID", "")
    tapper = str((cq.get("from") or {}).get("id", ""))
    if not owner or tapper != owner:
        logger.warning("Telegram callback from non-owner %s ignored.", tapper)
        telegram.answer_callback(cq["id"], "Not authorized.")
        return jsonify({"type": "ignored"})

    data = cq.get("data", "")
    action, _, proposal_id = data.partition(":")
    msg = PLAN_MSGS.pop(proposal_id, None)

    if action == "approve":
        result, err = _push_pending(proposal_id)
        if err:
            telegram.answer_callback(cq["id"], "Couldn't push — try again.")
            PLAN_MSGS[proposal_id] = msg  # keep context so a retry can still edit
            return jsonify({"error": "push failed"}), 502
        telegram.answer_callback(cq["id"], "Pushed to Spotify ✔")
        if msg:
            telegram.edit_message(msg["chat_id"], msg["message_id"],
                                  f"✔ Pushed to Spotify\n{result.get('url', '')}")
        logger.info("Proposal %s approved via Telegram.", proposal_id)
    elif action == "reject":
        playlist = PENDING_PROPOSALS.pop(proposal_id, None)
        if playlist is not None:
            _record_rejection(playlist, "rejected via Telegram")
        telegram.answer_callback(cq["id"], "Discarded ✘")
        if msg:
            telegram.edit_message(msg["chat_id"], msg["message_id"], "✘ Discarded")
        _event("user", "proposal rejected via Telegram")
        logger.info("Proposal %s rejected via Telegram.", proposal_id)
    else:
        telegram.answer_callback(cq["id"], "")
    return jsonify({"type": "ok"})
