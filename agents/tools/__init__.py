"""Agent tool registry — one module per tool.

Each tool module contributes its OpenAI-format schema and its callable;
this package aggregates them so agents just import TOOL_SCHEMAS/TOOL_REGISTRY
(or cherry-pick per agent). Adding a tool = add a module, register it here.
"""

from agents.tools.query_history import (
    MAX_ROWS,
    QUERY_HISTORY_SCHEMA,
    SCHEMA_DOC,
    query_history,
    validate_sql,
)
from agents.tools.audio_features import AUDIO_FEATURES_SCHEMA, get_audio_features
from agents.tools.discover import DISCOVER_SCHEMA, discover_new_tracks
from agents.tools.search_spotify import (
    ARTIST_TOP_TRACKS_SCHEMA,
    SEARCH_SPOTIFY_SCHEMA,
    artist_top_tracks,
    search_spotify,
)

TOOL_SCHEMAS = [QUERY_HISTORY_SCHEMA, SEARCH_SPOTIFY_SCHEMA, ARTIST_TOP_TRACKS_SCHEMA,
                AUDIO_FEATURES_SCHEMA, DISCOVER_SCHEMA]
TOOL_REGISTRY = {
    "query_history": query_history,
    "search_spotify": search_spotify,
    "artist_top_tracks": artist_top_tracks,
    "get_audio_features": get_audio_features,
    "discover_new_tracks": discover_new_tracks,
}
