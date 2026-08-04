"""Public list of DJ-pushed playlists with current feedback."""

from agents.store import playlists


def execute(limit=50):
    try:
        limit = int(limit)
    except (TypeError, ValueError):
        limit = 50
    limit = max(1, min(limit, 100))

    items = []
    for row in playlists.list_pushed(limit=limit):
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
        })
    return {"type": "playlists", "playlists": items}
