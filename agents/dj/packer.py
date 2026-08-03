"""Deterministic assembly: the model curates candidates, code selects the set.

Every constraint (duration window, artist cap, familiarity mix) is satisfied by
construction here, so the model is never asked to do arithmetic.
"""

from agents.dj import ground_truth
from agents.dj.constraints import (
    DEFAULT_DURATION_MIN,
    DURATION_TOLERANCE,
    MAX_PER_ARTIST,
    MAX_PLAYED_FRAC,
    effective_artist_cap,
)

TRACK_FIELDS = ("track_id", "track_name", "artist_name", "duration_ms",
                "familiarity", "reason")


def bucket(plays):
    """Familiarity from real play counts — the single source of truth."""
    if plays == 0:
        return "never"
    if plays <= 2:
        return "rare"
    if plays <= 15:
        return "familiar"
    return "heavy"


def interleave(selected):
    """Spread never-played tracks through the list instead of clumping them —
    front-loaded discovery gets skipped (an Evaluator finding)."""
    never = [t for t in selected if t["familiarity"] == "never"]
    rest = [t for t in selected if t["familiarity"] != "never"]
    if not never or not rest:
        return selected

    ordered, next_never, next_rest = [], 0, 0
    step = max(2, round(len(selected) / len(never)))
    for position in range(len(selected)):
        if (position % step == step - 1 and next_never < len(never)) or next_rest >= len(rest):
            ordered.append(never[next_never])
            next_never += 1
        else:
            ordered.append(rest[next_rest])
            next_rest += 1
    return ordered


def merge_pool(base, parsed, pool_acc):
    """Accumulate candidates across supply rounds (dedupe by id).

    Supply replies may carry ONLY the new entries — merging in code means the
    model never re-transcribes 30 track ids (it shirks that, we measured).
    Metadata (name/target/constraint) comes from the latest parse that has it.
    """
    seen = {c.get("track_id") for c in pool_acc}
    for candidate in (parsed.get("candidates") or []) + (parsed.get("tracks") or []):
        track_id = candidate.get("track_id")
        if track_id and track_id not in seen:
            seen.add(track_id)
            pool_acc.append(candidate)

    merged = dict(base or {}, **{k: v for k, v in parsed.items()
                                 if v not in (None, [], "") or k not in (base or {})})
    merged["candidates"] = list(pool_acc)
    merged.pop("tracks", None)
    return merged


def pack(playlist):
    """Returns (packed_playlist, supply_gap_min).

    `packed` is None only when nothing in the pool is valid; a `supply_gap_min`
    above zero means the valid pool couldn't reach the duration window, and the
    caller asks the model for MORE candidates — never for math.
    """
    playlist = playlist or {}
    pool = playlist.get("candidates") or playlist.get("tracks") or []
    real = ground_truth.reality(pool)
    if real is None:
        return None, None  # DB unreachable — caller falls back to the sanitizer

    target = playlist.get("target_duration_min") or DEFAULT_DURATION_MIN
    target_ms = target * 60000
    ceiling_ms = target_ms * (1 + DURATION_TOLERANCE)
    floor_ms = target_ms * (1 - DURATION_TOLERANCE)
    mostly_never = playlist.get("familiarity_constraint") == "mostly_never"
    artist_cap = effective_artist_cap(playlist)

    graded = _grade(pool, real)
    if not graded:
        return None, round(target, 1)
    graded.sort(key=lambda c: (not c["_keep"], -c["_fit"]))  # pins first, then fit

    selected, total_ms = _select(
        graded, target_ms, ceiling_ms, mostly_never, artist_cap)
    if not selected:
        return None, round(target, 1)

    packed = {
        "name": playlist.get("name") or "Untitled",
        "description": playlist.get("description") or "",
        "target_duration_min": target,
        "familiarity_constraint": playlist.get("familiarity_constraint") or "mixed",
        "total_duration_min": round(total_ms / 60000, 1),
        "tracks": [{k: t[k] for k in TRACK_FIELDS} for t in interleave(selected)],
    }
    if artist_cap != MAX_PER_ARTIST:
        packed["artist_cap"] = artist_cap
        reason = (playlist.get("artist_cap_reason") or "").strip()
        if reason:
            packed["artist_cap_reason"] = reason
    gap = round((target_ms - total_ms) / 60000, 1) if total_ms < floor_ms else 0
    return packed, gap


def _grade(pool, real):
    """Drop ids that exist nowhere or duplicate, and attach real metadata."""
    graded, seen = [], set()
    for candidate in pool:
        track_id = candidate.get("track_id")
        info = real.get(track_id)
        if not track_id or track_id in seen or info is None or not info.get("duration_ms"):
            continue
        seen.add(track_id)
        plays = info.get("plays", 0)
        graded.append({
            "track_id": track_id,
            "track_name": candidate.get("track_name") or "",
            "artist_name": info.get("artist") or candidate.get("artist_name") or "",
            "duration_ms": info["duration_ms"],
            "familiarity": bucket(plays),
            "reason": candidate.get("reason") or "",
            "_fit": float(candidate.get("fit") or 0.5),
            "_keep": bool(candidate.get("keep")),
            "_played": plays > 0,
        })
    return graded


def _select(graded, target_ms, ceiling_ms, mostly_never, artist_cap=MAX_PER_ARTIST):
    selected, per_artist, total_ms, played_n = [], {}, 0, 0
    for candidate in graded:
        if total_ms >= target_ms:
            break
        if total_ms + candidate["duration_ms"] > ceiling_ms:
            continue
        if per_artist.get(candidate["artist_name"], 0) >= artist_cap:
            continue
        # prefix-invariant: the mix holds at every step, so it holds at the end
        if mostly_never and candidate["_played"] and \
                (played_n + 1) > MAX_PLAYED_FRAC * (len(selected) + 1):
            continue
        selected.append(candidate)
        per_artist[candidate["artist_name"]] = per_artist.get(candidate["artist_name"], 0) + 1
        total_ms += candidate["duration_ms"]
        played_n += candidate["_played"]
    return selected, total_ms
