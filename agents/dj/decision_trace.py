"""Compact, auditable “why this mix” facts attached at propose time.

Facts come from the bias snapshot injected into the DJ + the packed playlist
+ verifier corrections. Model-authored track reasons stay on the tracks and
are labeled separately in the UI — never treated as ground truth.
"""


def attach_decision_trace(playlist, biases=None, violations=None):
    """Mutate playlist with decision_trace; return playlist (or None)."""
    if not playlist:
        return playlist
    playlist["decision_trace"] = build_decision_trace(
        playlist, biases or [], violations=violations or [],
    )
    return playlist


def build_decision_trace(playlist, biases, violations=None):
    """Pure builder — inputs in, JSON-serializable dict out."""
    playlist = playlist or {}
    biases = list(biases or [])
    violations = list(violations or [])
    tracks = playlist.get("tracks") or []

    bias_rows = [_bias_row(b, tracks) for b in biases]
    exploration = _exploration_heuristic(tracks, biases)
    summary = _summary_lines(bias_rows, exploration, violations, playlist)

    return {
        "version": 1,
        "facts": {
            "biases": bias_rows,
            "constraints": {
                "familiarity_constraint": playlist.get("familiarity_constraint"),
                "target_duration_min": playlist.get("target_duration_min"),
                "total_duration_min": playlist.get("total_duration_min"),
                "artist_cap": playlist.get("artist_cap"),
                "artist_cap_reason": playlist.get("artist_cap_reason"),
            },
            "verifier_corrections": violations,
            "exploration": exploration,
        },
        "summary": summary,
        "model_vs_facts": (
            "Summary lines above are derived from recorded biases and the "
            "packed playlist. Per-track 'reason' text is model-written, not verified."
        ),
    }


def _bias_row(bias, tracks):
    kind = bias.get("kind") or ""
    key = bias.get("key") or ""
    sample_n = int(bias.get("sample_n") or 0)
    matched = [
        t.get("track_id") for t in tracks
        if t.get("track_id") and _track_matches_bias(t, kind, key)
    ]
    return {
        "kind": kind,
        "key": key,
        "weight": bias.get("weight"),
        "sample_n": sample_n,
        "evidence": bias.get("evidence") or "",
        "weak": bool(bias.get("weak")) or sample_n < 3,
        "matched_track_ids": matched,
        "matched_n": len(matched),
    }


def _track_matches_bias(track, kind, key):
    if not key:
        return False
    needle = key.casefold()
    if kind == "artist":
        return needle in (track.get("artist_name") or "").casefold()
    if kind == "track":
        return needle in (track.get("track_name") or "").casefold()
    # genre/context: no durable field on packed tracks — can't claim a match.
    return False


def _exploration_heuristic(tracks, biases):
    """Tracks outside positive artist prefs. Honest: not an enforced quota."""
    positive_artists = [
        b for b in biases
        if b.get("kind") == "artist" and (b.get("weight") or 0) > 0
    ]
    n = len(tracks)
    if not n:
        return {
            "approx_pct": None,
            "track_ids": [],
            "method": "outside_positive_artist_prefs",
            "note": "No tracks to score.",
        }
    if not positive_artists:
        return {
            "approx_pct": None,
            "track_ids": [],
            "method": "outside_positive_artist_prefs",
            "note": (
                "No positive artist prefs were active — cannot estimate "
                "exploration share (quota is prompt-only today)."
            ),
        }

    outside = []
    for t in tracks:
        tid = t.get("track_id")
        if not tid:
            continue
        if not any(_track_matches_bias(t, "artist", b.get("key")) for b in positive_artists):
            outside.append(tid)
    pct = round(100.0 * len(outside) / n)
    return {
        "approx_pct": pct,
        "track_ids": outside,
        "method": "outside_positive_artist_prefs",
        "note": (
            "Heuristic share of tracks that do not match positive artist "
            "prefs — packer does not enforce the 15–20% exploration quota."
        ),
    }


def _summary_lines(bias_rows, exploration, violations, playlist):
    lines = []
    if not bias_rows:
        lines.append("No learned preferences were active for this mix.")
    else:
        for b in bias_rows:
            direction = "prefers" if (b.get("weight") or 0) > 0 else "leans away from"
            weak = " — weak evidence" if b.get("weak") else ""
            match = (
                f", matched {b['matched_n']} track(s) in this mix"
                if b["matched_n"] else ", no direct track match in this mix"
            )
            lines.append(
                f"{direction} {b['kind']} '{b['key']}' "
                f"({b.get('weight'):+0.2f}, n={b.get('sample_n', 0)}{weak}){match}"
            )

    pct = (exploration or {}).get("approx_pct")
    if pct is None:
        note = (exploration or {}).get("note")
        if note and bias_rows:
            lines.append(note)
    else:
        lines.append(
            f"About {pct}% of tracks sit outside positive artist prefs "
            "(heuristic, not an enforced quota)."
        )

    if violations:
        lines.append(f"Verifier repaired {len(violations)} packer issue(s).")
    else:
        lines.append("No verifier corrections.")

    fam = playlist.get("familiarity_constraint")
    if fam:
        lines.append(f"Familiarity constraint: {fam}.")
    return lines
