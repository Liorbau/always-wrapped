import os
from zoneinfo import ZoneInfo

DEFAULT_TZ = "Asia/Jerusalem"


def resolve_tz(client_tz=None):
    for candidate in ((client_tz or "").strip(), os.getenv("USER_TZ", DEFAULT_TZ), "UTC"):
        if not candidate:
            continue
        try:
            ZoneInfo(candidate)
        except Exception:
            continue
        return candidate
    return "UTC"
