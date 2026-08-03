"""The playlist constraints the packer enforces and the prompt advertises.

One definition each, so the prompt can never drift from the code that checks it.
"""

DEFAULT_DURATION_MIN = 60
MAX_COST_USD = 2.00
MAX_STEPS = 16
MAX_REPAIR_ROUNDS = 2
DURATION_TOLERANCE = 0.25
MAX_PER_ARTIST = 2
MAX_PLAYED_FRAC = 0.4  # never-heard playlists: played tracks stay <= this share

TOLERANCE_PCT = int(DURATION_TOLERANCE * 100)


def effective_artist_cap(playlist):
    """Max tracks per artist for this proposal.

    Default is MAX_PER_ARTIST. Raising it requires a non-empty
    artist_cap_reason — otherwise the default holds (no silent override).
    """
    playlist = playlist or {}
    raw = playlist.get("artist_cap")
    if raw is None or raw == "":
        return MAX_PER_ARTIST
    try:
        cap = int(raw)
    except (TypeError, ValueError):
        return MAX_PER_ARTIST
    if cap < 1:
        return MAX_PER_ARTIST
    if cap > MAX_PER_ARTIST and not (playlist.get("artist_cap_reason") or "").strip():
        return MAX_PER_ARTIST
    return cap
