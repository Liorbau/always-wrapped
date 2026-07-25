from app.modules.music import repository

DEFAULT_LIMIT = 50


def execute(limit=DEFAULT_LIMIT):
    return repository.recent_plays(limit)
