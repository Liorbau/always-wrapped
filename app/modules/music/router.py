"""Transport for the dashboard's data endpoints — parse, delegate, serialize."""

from flask import Blueprint, jsonify, request

from core.timezone import resolve_tz
from app.modules.music.orchestrators import (
    get_insight,
    get_records,
    get_top_artists,
    get_top_songs,
    list_history,
    refresh_library,
    search_library,
)

music_bp = Blueprint("music", __name__, url_prefix="/api")


@music_bp.get("/history")
def history():
    return jsonify(list_history.execute())


@music_bp.get("/stats/top-songs")
def top_songs():
    return jsonify(get_top_songs.execute(time_range=request.args.get("range", "all_time")))


@music_bp.get("/stats/top-artists")
def top_artists():
    return jsonify(get_top_artists.execute(time_range=request.args.get("range", "all_time")))


@music_bp.get("/insight")
def insight():
    return jsonify(get_insight.execute(tz=resolve_tz(request.args.get("tz"))))


@music_bp.get("/records")
def records():
    return jsonify(get_records.execute(tz=resolve_tz(request.args.get("tz"))))


@music_bp.get("/search")
def search():
    return jsonify(search_library.execute(
        request.args.get("q", "").strip(),
        time_range=request.args.get("range", "all_time"),
    ))


@music_bp.post("/refresh")
def refresh():
    return jsonify(refresh_library.execute())
