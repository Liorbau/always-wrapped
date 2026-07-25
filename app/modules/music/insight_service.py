"""Domain rules for the insight card: which facts are worth surfacing.

Produces structured candidates only. Wording and markup belong to the mapper,
so the randomness that picks a variant is decided here as data.
"""

import random

from app.modules.music import insight_repository as repo

SAMPLE_SIZE = 30
NEGLECT_DEPTH = 10
MISS_YOU_VARIANTS = 3


def hour_label(hour):
    if hour >= 22 or hour < 5:
        return "a night owl"
    if hour < 9:
        return "an early bird"
    if hour < 17:
        return "a daytime listener"
    return "an evening viber"


def neglected_favourite(artists, rng):
    """A long-term favourite absent from the last 7 days — the 'miss you' beat."""
    recent = repo.recently_played_artist_names(NEGLECT_DEPTH)
    for index, artist in enumerate(artists[:NEGLECT_DEPTH]):
        if artist["artist_name"] not in recent:
            return {
                "kind": "neglected_artist",
                "icon": "heart-crack",
                "artist_name": artist["artist_name"],
                "rank": index + 1,
                "variant": rng.randrange(MISS_YOU_VARIANTS),
            }
    return None


def build_candidates(rng=random):
    candidates = []

    songs = repo.most_played_songs(SAMPLE_SIZE)
    if songs:
        index = rng.randrange(len(songs))
        candidates.append({
            "kind": "top_song",
            "icon": "music",
            "rank": index + 1,
            "track_name": songs[index]["track_name"],
            "artist_name": songs[index]["artist_name"],
            "play_count": songs[index]["play_count"],
        })

    artists = repo.most_played_artists(SAMPLE_SIZE)
    if artists:
        index = rng.randrange(len(artists))
        candidates.append({
            "kind": "top_artist",
            "icon": "microphone",
            "rank": index + 1,
            "artist_name": artists[index]["artist_name"],
            "play_count": artists[index]["play_count"],
        })
        neglected = neglected_favourite(artists, rng)
        if neglected:
            candidates.append(neglected)

    hour = repo.peak_listening_hour()
    if hour is not None:
        candidates.append({
            "kind": "peak_hour",
            "icon": "clock",
            "hour": hour,
            "label": hour_label(hour),
        })

    totals = repo.library_totals()
    if totals:
        candidates.append({"kind": "totals", "icon": "chart-bar", **totals})

    return candidates


def pick(rng=random):
    candidates = build_candidates(rng)
    return rng.choice(candidates) if candidates else None
