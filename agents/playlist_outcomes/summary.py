"""Aggregates, cohorts, and Observatory one-liners."""

from agents.store import hitl, playlists
from agents.playlist_outcomes.queries import fetch_history_plays, last_bias_update_at
from agents.playlist_outcomes.score import outcome_for_playlist

DISCLAIMER = (
    "Descriptive only — not causal. Tiny n means weak signal; "
    "never invent outcomes for unplayed or ambiguous plays."
)


def learning_summary(limit=40):
    """Aggregate for Evaluator / activity / observatory."""
    limit = max(1, min(int(limit or 40), 100))
    pushed = playlists.list_pushed(limit=limit)
    hitl_counts = hitl.decision_counts()
    if not pushed:
        return {
            "type": "learning_outcomes",
            "hitl": hitl_counts,
            "n_playlists": 0,
            "aggregate": empty_aggregate(),
            "cohorts": None,
            "bias_cutoff": last_bias_update_at(),
            "disclaimer": DISCLAIMER,
            "per_playlist": [],
        }

    since = min((p.get("pushed_at") or "") for p in pushed) or None
    track_ids = sorted({
        t.get("track_id")
        for p in pushed
        for t in (p.get("tracks") or [])
        if t.get("track_id")
    })
    history = fetch_history_plays(since, track_ids)
    per = [
        outcome_for_playlist(row, history, feedback=playlists.feedback_for(row["id"]))
        for row in pushed
    ]

    cutoff = last_bias_update_at()
    return {
        "type": "learning_outcomes",
        "hitl": hitl_counts,
        "n_playlists": len(per),
        "aggregate": aggregate_outcomes(per),
        "cohorts": cohort_rollups(per, cutoff),
        "bias_cutoff": cutoff,
        "disclaimer": DISCLAIMER,
        "per_playlist": per,
    }


def aggregate_outcomes(outcomes):
    outcomes = list(outcomes or [])
    played = [o for o in outcomes if o.get("status") != "never_played"]
    skips = sum(o.get("n_skipped") or 0 for o in outcomes)
    completes = sum(o.get("n_completed") or 0 for o in outcomes)
    decided = skips + completes
    ratings = [o["mean_rating"] for o in outcomes if o.get("mean_rating") is not None]
    ttfs = [o["time_to_first_play_sec"] for o in outcomes
            if o.get("time_to_first_play_sec") is not None]
    return {
        "n": len(outcomes),
        "n_with_plays": len(played),
        "n_never_played": len(outcomes) - len(played),
        "skip_rate": round(skips / decided, 3) if decided else None,
        "completion_rate": round(completes / decided, 3) if decided else None,
        "mean_rating": round(sum(ratings) / len(ratings), 2) if ratings else None,
        "n_rated": len(ratings),
        "median_time_to_first_play_sec": median(ttfs),
    }


def cohort_rollups(outcomes, bias_cutoff):
    """Split by pushed_at vs last bias update. Descriptive, not causal."""
    if not bias_cutoff:
        return {
            "method": "last_bias_updated_at",
            "cutoff": None,
            "note": "No preference_bias rows — cannot split before/after learning.",
            "before": None,
            "after": None,
        }
    before, after = [], []
    for o in outcomes or []:
        ts = o.get("pushed_at") or ""
        (after if ts >= bias_cutoff else before).append(o)
    return {
        "method": "last_bias_updated_at",
        "cutoff": bias_cutoff,
        "note": (
            "Before/after last preference_bias.updated_at. "
            "Descriptive only; decay rewrites weights so cutoff is approximate."
        ),
        "before": aggregate_outcomes(before),
        "after": aggregate_outcomes(after),
    }


def observatory_line(summary=None):
    """One short dict for the Observatory costbar."""
    summary = summary or learning_summary(limit=40)
    agg = summary.get("aggregate") or {}
    hitl_c = summary.get("hitl") or {}
    cohorts = summary.get("cohorts") or {}
    before = (cohorts.get("before") or {}).get("skip_rate")
    after = (cohorts.get("after") or {}).get("skip_rate")
    trend = None
    if before is not None and after is not None:
        trend = "skip↓" if after < before else ("skip↑" if after > before else "skip→")
    return {
        "n_playlists": summary.get("n_playlists") or 0,
        "n_with_plays": agg.get("n_with_plays"),
        "skip_rate": agg.get("skip_rate"),
        "mean_rating": agg.get("mean_rating"),
        "approve_rate": hitl_c.get("approve_rate"),
        "cohort_trend": trend,
        "disclaimer": DISCLAIMER,
    }


def empty_aggregate():
    return {
        "n": 0, "n_with_plays": 0, "n_never_played": 0,
        "skip_rate": None, "completion_rate": None,
        "mean_rating": None, "n_rated": 0,
        "median_time_to_first_play_sec": None,
    }


def median(values):
    values = sorted(values or [])
    if not values:
        return None
    mid = len(values) // 2
    if len(values) % 2:
        return values[mid]
    return round((values[mid - 1] + values[mid]) / 2.0, 1)
