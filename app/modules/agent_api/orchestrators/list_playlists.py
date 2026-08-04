"""Public list of DJ-pushed playlists with feedback + outcome facts."""

from agents import playlist_outcomes
from agents.store import playlists


def execute(limit=50):
    try:
        limit = int(limit)
    except (TypeError, ValueError):
        limit = 50
    limit = max(1, min(limit, 100))

    rows = playlists.list_pushed(limit=limit)
    summary = playlist_outcomes.learning_summary(limit=limit)
    by_id = {o["playlist_id"]: o for o in summary.get("per_playlist") or []}

    items = []
    for row in rows:
        items.append({
            "id": row["id"],
            "spotify_playlist_id": row["spotify_playlist_id"],
            "url": row["url"],
            "name": row["name"],
            "description": row["description"],
            "tracks": row["tracks"],
            "context": row["context"],
            "pushed_at": row["pushed_at"],
            "feedback": playlists.feedback_for(row["id"]),
            "outcome": by_id.get(row["id"]),
        })
    return {
        "type": "playlists",
        "playlists": items,
        "learning_outcomes": {
            "hitl": summary.get("hitl"),
            "aggregate": summary.get("aggregate"),
            "cohorts": summary.get("cohorts"),
            "bias_cutoff": summary.get("bias_cutoff"),
            "disclaimer": summary.get("disclaimer"),
        },
    }
