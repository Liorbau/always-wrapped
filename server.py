"""Flask server providing REST API endpoints for Spotify listening history data.

This module serves listening history and analytics endpoints, querying the
SQLite database for recently played tracks and top songs.
"""

import os
import threading
import sqlite3

from flask import Flask, jsonify, render_template, request

from logging_config import configure_logger
from collect_songs import start_collector_service
from analytics import get_db_connection, get_top_songs, get_top_artists
from collect_songs import get_spotify_client, fetch_recent_tracks, save_tracks_to_db
from setup_db import create_database

logger = configure_logger(__name__)

app = Flask(__name__)


@app.route("/")
def index():
    """Serves the main dashboard page."""
    return render_template("index.html")


@app.route("/api/history", methods=["GET"])
def get_recent_tracks():
    """Return the last 50 songs listened to."""
    try:
        conn = get_db_connection()
        conn.row_factory = sqlite3.Row

        cursor = conn.cursor()
        cursor.execute(
            "SELECT * FROM listening_history ORDER BY played_at DESC LIMIT 50"
        )

        rows = cursor.fetchall()
        results = [dict(row) for row in rows]

        conn.close()
        return jsonify(results)

    except sqlite3.Error as exc:
        logger.error("Database error: %s", exc)
        return jsonify({"error": str(exc)}), 500


@app.route('/api/stats/top-songs', methods=['GET'])
def get_top_songs_api():
    # Get parameter from URL (e.g. ?range=7days), default to 'all_time'
    time_range = request.args.get('range', 'all_time')
    results = get_top_songs(limit=5, time_range=time_range)
    return jsonify(results)

@app.route('/api/stats/top-artists', methods=['GET'])
def get_top_artists_api():
    time_range = request.args.get('range', 'all_time')
    results = get_top_artists(limit=5, time_range=time_range)
    return jsonify(results)


@app.route("/api/refresh", methods=["POST"])
def refresh_data():
    """Forces a data sync with Spotify."""
    try:
        sp = get_spotify_client()
        if not sp:
            return jsonify({"error": "Failed to connect to Spotify"}), 500

        tracks = fetch_recent_tracks(sp)
        save_tracks_to_db(tracks)

        return jsonify({"status": "success", "count": len(tracks)})
    except sqlite3.Error as exc:
        return jsonify({"error": str(exc)}), 500


if __name__ == '__main__':
    logger.info("Initializing Database...")
    create_database()

    collector_thread = threading.Thread(target=start_collector_service, daemon=True)
    collector_thread.start()
    
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)
