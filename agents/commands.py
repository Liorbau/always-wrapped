"""Slash-command dictionary — one list for web chat and Telegram.

Add new commands here first, then wire the handler. Surfaces keep the help
text honest when a command exists on only one channel.
"""

# Each entry: cmd (canonical), usage (shown to the user), blurb, surfaces.
COMMANDS = (
    {
        "cmd": "/help",
        "usage": "/help",
        "blurb": "Show this command list",
        "surfaces": ("web", "telegram"),
    },
    {
        "cmd": "/start",
        "usage": "/start",
        "blurb": "Show this command list (Telegram)",
        "surfaces": ("telegram",),
    },
    {
        "cmd": "/spend",
        "usage": "/spend",
        "blurb": "LLM spend today / this week (Sun–today) / this month",
        "surfaces": ("web",),
    },
    {
        "cmd": "/plantime",
        "usage": "/plantime HH:MM | off",
        "blurb": "When the nightly Planner runs (or turn it off)",
        "surfaces": ("web", "telegram"),
    },
    {
        "cmd": "/plan",
        "usage": "/plan",
        "blurb": "Build tomorrow’s playlists from your calendar",
        "surfaces": ("telegram",),
    },
    {
        "cmd": "/timer",
        "usage": "/timer HH:MM <days> <what you want>",
        "blurb": "Standing playlist reminder (e.g. sun-thu or mon,wed)",
        "surfaces": ("telegram",),
    },
    {
        "cmd": "/timers",
        "usage": "/timers",
        "blurb": "List active timers",
        "surfaces": ("telegram",),
    },
    {
        "cmd": "/deltimer",
        "usage": "/deltimer <id>",
        "blurb": "Remove a timer (see /timers)",
        "surfaces": ("telegram",),
    },
)


def for_surface(surface):
    """Commands available on `web` or `telegram`."""
    surface = (surface or "").lower()
    return [c for c in COMMANDS if surface in c["surfaces"]]


def as_dicts(surface):
    """JSON-safe list for the API / chat UI."""
    return [
        {"cmd": c["cmd"], "usage": c["usage"], "blurb": c["blurb"]}
        for c in for_surface(surface)
    ]


def help_text(surface):
    """Plain-text dictionary for /help replies and Telegram USAGE."""
    lines = ["Usage:"]
    for c in for_surface(surface):
        lines.append(f"  {c['usage']} — {c['blurb']}")
    if surface == "web":
        lines.append("")
        lines.append("You can also just ask in plain language for a playlist,")
        lines.append("listening stats, or your Wrapped.")
    elif surface == "telegram":
        lines.append("")
        lines.append("Example: /timer 07:30 sun-thu a 50-min upbeat train playlist")
    return "\n".join(lines)
