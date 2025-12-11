"""Data extraction and analysis from db."""

import sqlite3
import logging
import os

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler()],
)
logger = logging.getLogger(__name__)

CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(CURRENT_DIR, "my_spotify_data.db")


def get_db_connection():
    try:
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        return conn
    except sqlite3.Error as exc:
        logger.error("Database connection failed: %s", exc)
        return None


def get_top_songs(limit=5, time_range='all_time'):
    """
    Returns the top listened songs, optionally filtered by time.
    time_range options: 'all_time', '7days', 'ytd'
    """
    conn = get_db_connection()
    if not conn:
        return []

    query = """
    SELECT 
        track_name, 
        artist_name, 
        album_image_url, 
        COUNT(*) as play_count
    FROM listening_history
    WHERE 1=1 
    """

    if time_range == '7days':
        query += " AND played_at >= datetime('now', '-7 days')"
    elif time_range == 'ytd':
        query += " AND played_at >= datetime('now', 'start of year')"
    
    query += """
    GROUP BY track_id
    ORDER BY play_count DESC
    LIMIT ?
    """

    cursor = conn.cursor()
    cursor.execute(query, (limit,))
    results = cursor.fetchall()
    conn.close()

    return [dict(row) for row in results]


def get_top_artists(limit=5, time_range='all_time'):
    """
    Returns the top artists, optionally filtered by time.
    """
    conn = get_db_connection()
    if not conn:
        return []

    query = """
    SELECT 
        artist_name, 
        COUNT(*) as play_count
    FROM listening_history
    WHERE 1=1
    """

    if time_range == '7days':
        query += " AND played_at >= datetime('now', '-7 days')"
    elif time_range == 'ytd':
        query += " AND played_at >= datetime('now', 'start of year')"

    query += """
    GROUP BY artist_name
    ORDER BY play_count DESC
    LIMIT ?
    """

    cursor = conn.cursor()
    cursor.execute(query, (limit,))
    results = cursor.fetchall()
    conn.close()

    return [dict(row) for row in results]