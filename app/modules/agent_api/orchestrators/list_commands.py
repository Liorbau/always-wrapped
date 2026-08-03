"""Slash-command dictionary for the chat UI and /help."""

from agents.commands import as_dicts, help_text


def for_surface(surface="web"):
    surface = (surface or "web").lower()
    if surface not in ("web", "telegram"):
        surface = "web"
    return {
        "type": "commands",
        "surface": surface,
        "commands": as_dicts(surface),
        "response": help_text(surface),
    }
