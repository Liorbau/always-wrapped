"""Pure reshapes between repository rows and the public JSON DTOs."""

import html

EMPTY_INSIGHT = {"text": "Keep listening to unlock insights!", "icon": "lightbulb"}

# The insight card is rendered as HTML so the numbers can be bold, which makes
# every interpolated name untrusted input.
NEGLECTED_PHRASINGS = (
    "<b>{artist}</b> misses you! Your <b>#{rank}</b> artist all time but nowhere this week",
    'Hey! <b>{artist}</b> says: "Remember me? I\'m your <b>#{rank}</b> artist!"',
    "<b>{artist}</b> is feeling lonely — your <b>#{rank}</b> all time but MIA this week",
)


def insight_to_dto(candidate):
    if candidate is None:
        return EMPTY_INSIGHT
    return {"text": _insight_text(candidate), "icon": candidate["icon"]}


def _insight_text(candidate):
    kind = candidate["kind"]
    if kind == "top_song":
        return (
            f"<b>{html.escape(candidate['track_name'])}</b> by "
            f"{html.escape(candidate['artist_name'])} is your "
            f"<b>#{candidate['rank']}</b> most played song with "
            f"{candidate['play_count']} plays"
        )
    if kind == "top_artist":
        return (
            f"<b>{html.escape(candidate['artist_name'])}</b> is your "
            f"<b>#{candidate['rank']}</b> most listened artist with "
            f"{candidate['play_count']} plays"
        )
    if kind == "neglected_artist":
        return NEGLECTED_PHRASINGS[candidate["variant"]].format(
            artist=html.escape(candidate["artist_name"]), rank=candidate["rank"]
        )
    if kind == "peak_hour":
        return (
            f"You listen the most around <b>{candidate['hour']}:00</b> - "
            f"you're {candidate['label']}"
        )
    return (
        f"You've logged <b>{candidate['plays']}</b> plays across "
        f"<b>{candidate['songs']}</b> unique songs from "
        f"<b>{candidate['artists']}</b> artists"
    )


def artist_to_dto(row, image_url=None):
    return {
        "artist_name": row["artist_name"],
        "play_count": row["play_count"],
        "artist_image_url": image_url if image_url is not None else row.get("artist_image_url"),
        "artist_id": row.get("artist_id"),
    }


def search_hit_to_dto(row, kind, rank):
    return dict(row, type=kind, rank=rank)
