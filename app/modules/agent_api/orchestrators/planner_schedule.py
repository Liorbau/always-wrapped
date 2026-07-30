"""Read / update the nightly Planner schedule (alarm clock, not a run trigger)."""

import datetime

from agents import timers
from app.errors import validation_error


def current():
    at = timers.planner_time()
    return {"at": at, "enabled": at is not None}


def apply(at):
    """`at` is 'HH:MM', None/''/'off' to disable."""
    if at is None or (isinstance(at, str) and at.strip().lower() in ("", "off")):
        timers.set_planner_time(None)
        return current()
    if not isinstance(at, str):
        raise validation_error("at must be HH:MM or null/off.")
    try:
        normalized = datetime.datetime.strptime(at.strip(), "%H:%M").strftime("%H:%M")
    except ValueError:
        raise validation_error(f"Bad time {at!r} — use HH:MM or off.")
    timers.set_planner_time(normalized)
    return current()


def from_chat_command(message):
    """Handle /plantime … — returns a chat reply payload, never starts a run."""
    parsed = timers.parse_plantime(message)
    if "error" in parsed:
        return {"type": "plantime", "response": parsed["error"], **current()}
    if not parsed:
        cur = current()
        label = cur["at"] if cur["enabled"] else "off"
        return {
            "type": "plantime",
            "response": f"Nightly Planner is {label}. Set it: /plantime HH:MM | off",
            **cur,
        }
    timers.set_planner_time(parsed["at"])
    cur = current()
    label = cur["at"] if cur["enabled"] else "off"
    return {
        "type": "plantime",
        "response": f"Nightly Planner set to {label}.",
        **cur,
    }
