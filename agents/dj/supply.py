"""What we say (or do) when the candidate pool can't fill the duration window.

The model is only ever asked for MORE candidates — a fetch task. Assembly and
arithmetic stay in the packer.
"""

from agents.dj import candidates, language
from agents.dj.constraints import DEFAULT_DURATION_MIN, effective_artist_cap
from core.logging import configure_logger

logger = configure_logger(__name__)

RESERVE_FIT = 0.3  # below any model-curated score, so real picks always outrank
RESERVE_LIMIT = 60
MIN_NEW_TRACKS = 6
MINUTES_PER_TRACK = 3.5

WITHHOLD_REASONS = {
    "max_steps_reached": "I ran out of my step budget while gathering tracks",
    "cost_budget_reached": "I hit my cost budget for a single request",
    "cancelled": "the run was stopped",
}


def _packed_names(packed):
    return [t.get("track_name") or "" for t in (packed or {}).get("tracks") or []]


def reserve_topup(playlist, packed):
    """Last resort, code-side: the user's own most-played history, injected at a
    low fit so any model-curated candidate outranks it. Never for mostly_never."""
    hebrew = language.mostly_hebrew(_packed_names(packed))
    have = {c.get("track_id") for c in playlist.get("candidates") or []}

    added = 0
    for line in candidates.gap_candidates(list(have), limit=RESERVE_LIMIT, hebrew_only=hebrew):
        track_id, rest = line.split(" | ", 1)
        if track_id in have:
            continue
        playlist.setdefault("candidates", []).append({
            "track_id": track_id,
            "track_name": rest.split(" | ", 1)[0],
            "fit": RESERVE_FIT,
            "reason": "reserve pick from your own most-played",
        })
        added += 1

    if added:
        logger.info("Reserve top-up injected %d history candidates (hebrew=%s)", added, hebrew)
    return playlist


def supply_message(playlist, packed, gap_min, dj=None):
    target = (playlist or {}).get("target_duration_min") or DEFAULT_DURATION_MIN
    got = (packed or {}).get("total_duration_min", 0)
    cap = effective_artist_cap(playlist)
    lines = [
        f"SUPPLY CHECK: your valid candidates fill only {got} min of the ~{target:.0f} min "
        f"target (about {gap_min:.0f} min short after enforcing the artist cap and mix).",
        "Reply in the same JSON format but put ONLY the NEW candidates in \"candidates\" — "
        "code merges them with your existing pool, so do not repeat earlier ones. "
        f"Add at least {max(MIN_NEW_TRACKS, int(gap_min / MINUTES_PER_TRACK))} new tracks "
        f"(max {cap} usable per artist for this request).",
    ]

    if (playlist or {}).get("familiarity_constraint") == "mostly_never":
        lines += _never_supply(dj, packed)
    else:
        lines += _history_supply(packed)
    return "\n".join(lines)


def _never_supply(dj, packed):
    leftovers = candidates.unused_discoveries(dj, {"tracks": (packed or {}).get("tracks") or []})
    if not leftovers:
        return ["\nThe user wants NEVER-played tracks: do NOT add tracks from their "
                "history. Call discover_new_tracks again with different theme phrasings."]
    return ["\nVERIFIED-never-played candidates you already fetched but didn't "
            "include (id|title|artist|ms) — add these first:"] + \
           ["  " + line for line in leftovers]


def _history_supply(packed):
    hebrew = language.mostly_hebrew(_packed_names(packed))
    exclude = [t.get("track_id") for t in (packed or {}).get("tracks") or []]
    found = candidates.gap_candidates(exclude, hebrew_only=hebrew)
    if not found:
        return []
    return ["\nCandidates from the history you may add if they fit the request "
            "(id | track — artist | ms | plays | genres):"] + \
           ["  " + line for line in found]


def withhold_explanation(last_response, violations, status):
    """Specific, actionable failure message — never a generic shrug."""
    parts = [WITHHOLD_REASONS.get(status, "I couldn't finish the build")]
    if violations:
        parts.append("last check failed on: " + "; ".join(violations))
    prefix = (last_response + "\n\n") if last_response else ""
    return (prefix + " — ".join(parts) + ". Ideas that usually work: shorten the "
            "target (e.g. 1 hour), allow songs you've heard rarely instead of "
            "only never-played, or drop the mood filter. Tell me which to try.")
