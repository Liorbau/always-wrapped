"""Upsert multi-criteria ratings for one pushed playlist."""

from agents.store import playlists
from app.errors import not_found, validation_error


def execute(playlist_id, body):
    playlist_id = (playlist_id or "").strip()
    if not playlist_id:
        raise validation_error("Missing playlist id.")
    if playlists.get(playlist_id) is None:
        raise not_found("Unknown playlist.")

    body = body or {}
    # Omit note → leave existing notes; "" clears; string sets.
    note = body["note"] if "note" in body else None
    scores = _scores_from_body(body)
    if not scores:
        raise validation_error(
            "Provide criterion+score, or scores:{criterion: score}.",
            {"criteria": sorted(playlists.CRITERIA)},
        )

    saved = []
    for criterion, score in scores:
        if criterion not in playlists.CRITERIA:
            raise validation_error(
                f"Unknown criterion {criterion!r}.",
                {"criteria": sorted(playlists.CRITERIA)},
            )
        try:
            score = float(score)
        except (TypeError, ValueError):
            raise validation_error(f"Score for {criterion!r} must be a number.")
        if score < 0 or score > 5:
            raise validation_error(f"Score for {criterion!r} must be 0..5.")
        if not playlists.upsert_feedback(playlist_id, criterion, score, note=note):
            raise validation_error(f"Could not save {criterion!r}.")
        saved.append(criterion)

    return {
        "type": "playlist_feedback",
        "playlist_id": playlist_id,
        "saved": saved,
        "feedback": playlists.feedback_for(playlist_id),
    }


def _scores_from_body(body):
    """Normalize single {criterion, score} or {scores: {...}} into [(criterion, score)]."""
    if isinstance(body.get("scores"), dict) and body["scores"]:
        return list(body["scores"].items())
    if body.get("criterion") is not None:
        return [(body.get("criterion"), body.get("score"))]
    return []
