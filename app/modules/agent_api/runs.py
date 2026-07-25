"""The run registry: one agent run at a time, bounded history, live step feed."""

import threading
import time
import uuid

from app.errors import conflict, not_found
from core.logging import configure_logger

logger = configure_logger(__name__)

MAX_RUNS = 40
STALE_RUN_S = 300

RUNS = {}

lock = threading.Lock()
_active = {"id": None}

TOOL_LABELS = {
    "query_history": "exploring your history",
    "search_spotify": "searching Spotify",
    "artist_top_tracks": "collecting candidate tracks",
    "get_audio_features": "checking the mood",
    "discover_new_tracks": "hunting new music",
}


def step_label(entry):
    """Terse, high-level activity phrase for the live status line."""
    if entry["type"] == "tool_call":
        return TOOL_LABELS.get(entry["tool"], "working")
    if entry["type"] == "compaction":
        return "organizing thoughts"
    return "assembling the answer"


def claim_slot():
    """Reserve the single run slot, reaping a run that has clearly wedged."""
    active_id = _active["id"]
    if not active_id or RUNS[active_id]["done"]:
        return
    if time.time() - RUNS[active_id].get("started", 0) <= STALE_RUN_S:
        raise conflict("An agent is already working — wait for it to finish.")
    RUNS[active_id]["harness"].cancelled = True
    RUNS[active_id]["done"] = True
    RUNS[active_id]["error"] = "Run timed out."
    _active["id"] = None


def register(harness, kind):
    run_id = uuid.uuid4().hex[:12]
    RUNS[run_id] = {
        "harness": harness,
        "kind": kind,
        "done": False,
        "result": None,
        "error": None,
        "started": time.time(),
    }
    _active["id"] = run_id
    _evict_finished()
    return run_id


def release(run_id):
    """Never clear a newer run's slot."""
    if _active["id"] == run_id:
        _active["id"] = None


def _evict_finished():
    while len(RUNS) > MAX_RUNS:
        for run_id, run in list(RUNS.items()):
            if run["done"] and run_id != _active["id"]:
                del RUNS[run_id]
                break
        else:
            return


def get(run_id):
    run = RUNS.get(run_id)
    if run is None:
        raise not_found("Unknown run.")
    return run


def status(run_id):
    run = get(run_id)
    payload = {
        "done": run["done"],
        "steps": [step_label(e) for e in list(run["harness"].trajectory)],
    }
    if run["done"]:
        payload["result"] = run["result"]
        payload["error"] = run["error"]
    return payload


def stop(run_id):
    run = get(run_id)
    if not run["done"]:
        run["harness"].cancelled = True
        run["done"] = True  # the cancelled flag makes the worker exit its loop
        run["result"] = {"type": "answer", "response": "Stopped. Ask me anything."}
        with lock:
            release(run_id)
        logger.info("Run %s stopped by user.", run_id)
    return {"type": "stopped"}


def active_snapshot():
    run_id = _active["id"]
    if not run_id or run_id not in RUNS or RUNS[run_id]["done"]:
        return None
    run = RUNS[run_id]
    trajectory = list(run["harness"].trajectory)
    return {
        "agent": run["kind"],
        "doing": step_label(trajectory[-1]) if trajectory else "thinking",
        "steps": len(trajectory),
        "cost": round(run["harness"].metadata.get("cost_usd", 0), 4),
    }


def clear():
    RUNS.clear()
    _active["id"] = None
