"""Per-playlist outcome scoring from shelf tracks × classified plays."""

from agents.playlist_outcomes.classify import classify_gaps, seconds_between


def outcome_for_playlist(playlist, history_plays, feedback=None):
    """Score one pushed playlist against history rows.

    Filters to playlist track_ids with played_at >= pushed_at.
    """
    playlist = playlist or {}
    track_ids = [
        t.get("track_id") for t in (playlist.get("tracks") or [])
        if t.get("track_id")
    ]
    track_set = set(track_ids)
    pushed_at = playlist.get("pushed_at") or ""

    relevant = [
        p for p in (history_plays or [])
        if p.get("track_id") in track_set
        and (not pushed_at or (p.get("played_at") or "") >= pushed_at)
    ]
    classified = classify_gaps(relevant)

    n_tracks = len(track_ids)
    played_ids = {c["track_id"] for c in classified}
    n_completed = sum(1 for c in classified if c["outcome"] == "completed")
    n_skipped = sum(1 for c in classified if c["outcome"] == "skipped")
    n_unknown = sum(1 for c in classified if c["outcome"] == "unknown")
    decided = n_completed + n_skipped

    if not classified:
        status = "never_played"
    elif not played_ids:
        status = "never_played"
    elif len(played_ids) < n_tracks:
        status = "partial"
    else:
        status = "observed"

    scores = {
        f["criterion"]: f["score"]
        for f in (feedback or [])
        if f.get("criterion") is not None and f.get("score") is not None
    }
    mean_rating = (
        round(sum(scores.values()) / len(scores), 2) if scores else None
    )

    first_play = classified[0]["played_at"] if classified else None
    ttf = seconds_between(pushed_at, first_play) if first_play else None

    return {
        "playlist_id": playlist.get("id"),
        "name": playlist.get("name"),
        "pushed_at": pushed_at,
        "status": status,
        "n_tracks": n_tracks,
        "n_played_unique": len(played_ids),
        "n_plays": len(classified),
        "n_completed": n_completed,
        "n_skipped": n_skipped,
        "n_unknown": n_unknown,
        "skip_rate": round(n_skipped / decided, 3) if decided else None,
        "completion_rate": round(n_completed / decided, 3) if decided else None,
        "time_to_first_play_sec": ttf,
        "ratings": scores,
        "mean_rating": mean_rating,
        "exploration": exploration_outcomes(playlist, classified, track_set),
        "attribution": "track_played_after_push",
        "note": (
            "Never played after push." if status == "never_played"
            else "Plays matched by track_id after push — not proven playlist-sourced."
        ),
    }


def exploration_outcomes(playlist, classified, track_set):
    ctx = playlist.get("context") or {}
    trace = ctx.get("decision_trace") if isinstance(ctx, dict) else None
    if not isinstance(trace, dict):
        trace = playlist.get("decision_trace")
    facts = (trace or {}).get("facts") or {}
    exploration = facts.get("exploration") or {}
    flagged = [
        tid for tid in (exploration.get("track_ids") or [])
        if tid in track_set
    ]
    if not flagged:
        return None
    flagged_set = set(flagged)
    rows = [c for c in classified if c["track_id"] in flagged_set]
    skips = sum(1 for c in rows if c["outcome"] == "skipped")
    completes = sum(1 for c in rows if c["outcome"] == "completed")
    decided = skips + completes
    return {
        "n_flagged": len(flagged),
        "n_played": len({c["track_id"] for c in rows}),
        "n_skipped": skips,
        "n_completed": completes,
        "skip_rate": round(skips / decided, 3) if decided else None,
        "note": "Among decision_trace exploration-heuristic track_ids only.",
    }
