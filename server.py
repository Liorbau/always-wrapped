"""Flask server providing REST API endpoints for Spotify listening history data.

This module serves listening history and analytics endpoints, querying the
SQLite database for recently played tracks and top songs.
"""

import os
import threading

from flask import Flask, jsonify, render_template, request

from logging_config import configure_logger
from collect_songs import start_collector_service
from analytics import get_top_songs, get_top_artists, search_music, get_random_insight
from db_config import get_db_connection
from collect_songs import get_spotify_client, fetch_recent_tracks, save_tracks_to_db
from setup_db import create_database

logger = configure_logger(__name__)

app = Flask(__name__)


def enrich_top_artists_missing_images(artists):
    """Use Spotify only when ``artist_image_url`` is missing (legacy rows).

    Prefer batch ``artists?ids=`` when ``artist_id`` is known; otherwise
    catalog search by name as a last resort.
    """
    if not artists:
        return artists

    missing = [row for row in artists if not row.get("artist_image_url")]
    if not missing:
        return [
            {
                "artist_name": row["artist_name"],
                "play_count": row["play_count"],
                "artist_image_url": row.get("artist_image_url"),
            }
            for row in artists
        ]

    sp = get_spotify_client()

    ids_ordered = []
    seen_id = set()
    for row in missing:
        aid = row.get("artist_id")
        if aid and aid not in seen_id:
            seen_id.add(aid)
            ids_ordered.append(aid)

    id_to_url = {}
    if ids_ordered and sp:
        try:
            for i in range(0, len(ids_ordered), 50):
                chunk = ids_ordered[i : i + 50]
                resp = sp.artists(chunk)
                for a in resp.get("artists") or []:
                    if not a:
                        continue
                    images = a.get("images") or []
                    id_to_url[a["id"]] = images[0]["url"] if images else None
        except Exception as exc:
            logger.warning("Top artists: batch artist fetch failed: %s", exc)

    def _url_from_artist_obj(a):
        if not a:
            return None
        imgs = a.get("images") or []
        return imgs[0]["url"] if imgs else None

    def _search_by_name(name, preferred_id):
        if not sp or not name or not str(name).strip():
            return None
        safe = str(name).strip().replace('"', "")
        try:
            res = sp.search(
                q=f'artist:"{safe}"',
                type="artist",
                limit=5,
            )
        except Exception as exc:
            logger.warning("Top artists: search failed for %r: %s", name, exc)
            return None
        items = (res.get("artists") or {}).get("items") or []
        if not items:
            return None
        pick = None
        if preferred_id:
            pick = next((x for x in items if x.get("id") == preferred_id), None)
        if pick is None:
            needle = safe.lower()
            pick = next(
                (x for x in items if (x.get("name") or "").lower() == needle),
                items[0],
            )
        return _url_from_artist_obj(pick)

    enriched = []
    for row in artists:
        url = row.get("artist_image_url")
        aid = row.get("artist_id")

        if not url and aid:
            url = id_to_url.get(aid)

        if not url:
            url = _search_by_name(row.get("artist_name"), aid)

        enriched.append(
            {
                "artist_name": row["artist_name"],
                "play_count": row["play_count"],
                "artist_image_url": url,
            }
        )
    return enriched


@app.route("/")
def index():
    """Serves the main dashboard page."""
    return render_template("index.html")


@app.route("/api/history", methods=["GET"])
def get_recent_tracks():
    """Return the last 50 songs listened to."""
    try:
        conn, _ = get_db_connection()
        if not conn:
            return jsonify({"error": "Database connection failed"}), 500

        cursor = conn.cursor()
        cursor.execute(
            "SELECT * FROM listening_history ORDER BY played_at DESC LIMIT 50"
        )

        columns = [col[0] for col in cursor.description]
        rows = cursor.fetchall()
        results = [dict(zip(columns, row)) for row in rows]

        conn.close()
        return jsonify(results)

    except Exception as exc:
        logger.error("Database error: %s", exc)
        return jsonify({"error": str(exc)}), 500


@app.route("/api/stats/top-songs", methods=["GET"])
def get_top_songs_api():
    # Get parameter from URL (e.g. ?range=7days), default to 'all_time'
    time_range = request.args.get("range", "all_time")
    results = get_top_songs(limit=5, time_range=time_range)
    return jsonify(results)


@app.route("/api/stats/top-artists", methods=["GET"])
def get_top_artists_api():
    time_range = request.args.get("range", "all_time")
    results = get_top_artists(limit=5, time_range=time_range)
    results = enrich_top_artists_missing_images(results)
    return jsonify(results)


@app.route("/api/insight", methods=["GET"])
def insight_api():
    return jsonify(get_random_insight())


@app.route("/api/search", methods=["GET"])
def search_api():
    query = request.args.get("q", "").strip()
    time_range = request.args.get("range", "all_time")
    if not query:
        return jsonify([])
    results = search_music(query, time_range=time_range)
    return jsonify(results)


@app.route("/api/refresh", methods=["POST"])
def refresh_data():
    """Forces a data sync with Spotify."""
    try:
        sp = get_spotify_client()
        if not sp:
            return jsonify({"error": "Failed to connect to Spotify"}), 500

        tracks = fetch_recent_tracks(sp)
        save_tracks_to_db(tracks, sp)

        return jsonify({"status": "success", "count": len(tracks)})
    except Exception as exc:
        return jsonify({"error": str(exc)}), 500


if __name__ == "__main__":
    logger.info("Initializing Database...")
    create_database()

    collector_thread = threading.Thread(target=start_collector_service, daemon=True)
    collector_thread.start()

    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
