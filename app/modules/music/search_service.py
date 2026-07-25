"""Search rules: a bare '#12' is a rank lookup, anything else a substring match."""

from app.modules.music import repository
from app.modules.music.mappers import search_hit_to_dto

MAX_HITS_PER_KIND = 5


def search(query, time_range="all_time"):
    rank = _as_rank(query)
    if rank is not None:
        return _by_rank(rank, time_range)
    return _by_text(query, time_range)


def _as_rank(query):
    candidate = query.strip().lstrip("#")
    return int(candidate) if candidate.isdigit() else None


def _by_rank(rank, time_range):
    if rank < 1:
        return []
    hits = []
    for row in repository.songs_by_rank(time_range, offset=rank - 1):
        hits.append(search_hit_to_dto(row, "song", rank))
    for row in repository.artists_by_rank(time_range, offset=rank - 1):
        hits.append(search_hit_to_dto(row, "artist", rank))
    return hits


def _by_text(query, time_range):
    needle = query.lower()
    hits = []

    for index, row in enumerate(repository.songs_by_rank(time_range)):
        if needle in row["track_name"].lower() or needle in row["artist_name"].lower():
            hits.append(search_hit_to_dto(row, "song", index + 1))
            if sum(h["type"] == "song" for h in hits) >= MAX_HITS_PER_KIND:
                break

    artist_hits = 0
    for index, row in enumerate(repository.artists_by_rank(time_range)):
        if needle in row["artist_name"].lower():
            hits.append(search_hit_to_dto(row, "artist", index + 1))
            artist_hits += 1
            if artist_hits >= MAX_HITS_PER_KIND:
                break

    return hits
