"""Independent constraint check against the DB — code, not vibes.

The packer builds compliant lists by construction, so anything the verifier
catches is a packer bug; `sanitize` is the repair that still ships something.
"""

from agents.dj import ground_truth
from agents.dj.constraints import (
    DEFAULT_DURATION_MIN,
    DURATION_TOLERANCE,
    MAX_PER_ARTIST,
    MAX_PLAYED_FRAC,
)


def verify_playlist(playlist):
    """Returns a list of violation strings (empty = the playlist passes)."""
    tracks = (playlist or {}).get("tracks") or []
    if not tracks:
        return ["playlist has no tracks"]
    if any(not t.get("track_id") for t in tracks):
        return ["some tracks are missing a track_id"]

    real = ground_truth.reality(tracks)
    if real is None:
        return ["verifier could not reach the database"]

    violations = _duplicate_violations(tracks)
    per_artist, total_ms = {}, 0
    for track in tracks:
        info = real.get(track["track_id"])
        if info is None:
            violations.append(
                f"track_id {track['track_id']!r} ({track.get('track_name')}) does not exist "
                "in the listening history or the Spotify catalog"
            )
            continue
        total_ms += info["duration_ms"] or 0
        per_artist[info["artist"]] = per_artist.get(info["artist"], 0) + 1

    for artist, count in per_artist.items():
        if count > MAX_PER_ARTIST:
            violations.append(f"{count} tracks by {artist} (max {MAX_PER_ARTIST} per artist)")

    violations += _familiarity_violations(playlist, tracks, real)
    violations += _duration_violations(playlist, total_ms)
    return violations


def _duplicate_violations(tracks):
    violations, seen = [], set()
    for track in tracks:
        track_id = track.get("track_id")
        if track_id in seen:
            violations.append(
                f"duplicate track in playlist: {track.get('track_name')} ({track_id})"
            )
        seen.add(track_id)
    return violations


def _familiarity_violations(playlist, tracks, real):
    """Labels must match reality, and a declared 'never' mix must actually hold."""
    violations, played = [], 0
    for track in tracks:
        info = real.get(track.get("track_id"))
        if not info or info["plays"] <= 0:
            continue
        played += 1
        if track.get("familiarity") == "never":
            violations.append(
                f"{track.get('track_name')} is labeled 'never' but has {info['plays']} plays"
            )

    if (playlist or {}).get("familiarity_constraint") == "mostly_never" and tracks:
        if played / len(tracks) > MAX_PLAYED_FRAC:
            violations.append(
                f"{played}/{len(tracks)} tracks were already played — the user asked "
                "for never-heard music (played tracks must stay under 40%); replace "
                "played tracks with new discoveries, do not just remove them"
            )
    return violations


def _duration_violations(playlist, total_ms):
    target_min = (playlist or {}).get("target_duration_min") or DEFAULT_DURATION_MIN
    total_min = total_ms / 60000
    low = target_min * (1 - DURATION_TOLERANCE)
    high = target_min * (1 + DURATION_TOLERANCE)
    if low <= total_min <= high:
        return []
    return [
        f"real total duration is {total_min:.1f} min; target {target_min} min "
        f"requires {low:.1f}-{high:.1f} min"
    ]


def sanitize(playlist):
    """Code-level repair of a proposal that still has violations.

    Duration is a preference, not a safety property — never withhold over it.
    Returns (playlist, note) where note discloses a duration miss, or
    (None, None) when nothing valid remains.
    """
    tracks = (playlist or {}).get("tracks") or []
    real = ground_truth.reality(tracks) or {}
    mostly_never = (playlist or {}).get("familiarity_constraint") == "mostly_never"

    kept = _drop_invalid(tracks, real)
    if mostly_never:
        kept = _trim_played(kept, real)
    if not kept:
        return None, None

    total_ms = sum((real.get(t.get("track_id")) or {}).get("duration_ms") or 0 for t in kept)
    total_min = total_ms / 60000
    repaired = dict(playlist, tracks=kept, total_duration_min=round(total_min, 1))

    target = repaired.get("target_duration_min") or DEFAULT_DURATION_MIN
    note = None
    if not target * (1 - DURATION_TOLERANCE) <= total_min <= target * (1 + DURATION_TOLERANCE):
        note = (f"Heads up: this came out at ~{total_min:.0f} min vs the ~{target} min "
                "you asked for — it's the best verified set I found. Approve it, or "
                "ask me to extend/shorten it.")
    return repaired, note


def _drop_invalid(tracks, real):
    """Hallucinated ids, duplicates, and per-artist overflow."""
    kept, per_artist, kept_ids = [], {}, set()
    for track in tracks:
        track_id = track.get("track_id")
        info = real.get(track_id)
        if info is None or track_id in kept_ids:
            continue
        if per_artist.get(info["artist"], 0) >= MAX_PER_ARTIST:
            continue
        kept_ids.add(track_id)
        per_artist[info["artist"]] = per_artist.get(info["artist"], 0) + 1
        kept.append(track)
    return kept


def _trim_played(kept, real):
    """Enforce the never-heard mix on the FINAL list, matching the verifier's rule."""
    max_played = int(MAX_PLAYED_FRAC * len(kept))
    trimmed, played_kept = [], 0
    for track in kept:
        if (real.get(track.get("track_id")) or {}).get("plays", 0) > 0:
            if played_kept >= max_played:
                continue
            played_kept += 1
        trimmed.append(track)
    return trimmed
