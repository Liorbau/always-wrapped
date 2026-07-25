from app.modules.music import search_service


def execute(query, time_range="all_time"):
    if not query:
        return []
    return search_service.search(query, time_range)
