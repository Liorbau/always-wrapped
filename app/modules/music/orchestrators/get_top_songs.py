from app.modules.music import repository

DEFAULT_LIMIT = 5


def execute(limit=DEFAULT_LIMIT, time_range="all_time"):
    return repository.top_songs(limit, time_range)
