from app.modules.music import artist_images, mappers, repository

DEFAULT_LIMIT = 5


def execute(limit=DEFAULT_LIMIT, time_range="all_time"):
    rows = repository.top_artists(limit, time_range)
    return [mappers.artist_to_dto(row) for row in artist_images.enrich_missing_images(rows)]
