"""Data extraction and analysis from db."""

import logging
import os

from db_config import get_db_connection, get_placeholder

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler()],
)
logger = logging.getLogger(__name__)

CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(CURRENT_DIR, "my_spotify_data.db")


def get_top_songs(limit=5, time_range="all_time"):
    """
    Returns the top listened songs, optionally filtered by time.
    time_range options: 'all_time', '7days', 'ytd'
    """
    conn, driver = get_db_connection()
    if not conn:
        return []
    p = get_placeholder(driver)

    query = """
    SELECT 
        track_name, 
        artist_name, 
        album_image_url, 
        COUNT(*) as play_count
    FROM listening_history
    WHERE 1=1 
    """

    if time_range == "7days":
        if driver == "postgres":
            query += " AND played_at::timestamp >= (NOW() - INTERVAL '7 days')::text"
        else:
            query += " AND played_at >= datetime('now', '-7 days')"
    elif time_range == "ytd":
        if driver == "postgres":
            query += " AND played_at::timestamp >= (date_trunc('year', NOW()))::text"
        else:
            query += " AND played_at >= datetime('now', 'start of year')"

    query += f"""
    GROUP BY track_name, artist_name, album_image_url
    ORDER BY play_count DESC
    LIMIT {p}
    """

    cursor = conn.cursor()
    cursor.execute(query, (limit,))

    columns = [col[0] for col in cursor.description]
    results = [dict(zip(columns, row)) for row in cursor.fetchall()]

    conn.close()
    return results


def get_top_artists(limit=5, time_range="all_time"):
    """
    Returns the top artists, optionally filtered by time.
    """
    conn, driver = get_db_connection()
    if not conn:
        return []
    p = get_placeholder(driver)

    query = """
    SELECT 
        artist_name, 
        COUNT(*) as play_count
    FROM listening_history
    WHERE 1=1
    """

    if time_range == "7days":
        if driver == "postgres":
            query += " AND played_at::timestamp >= (NOW() - INTERVAL '7 days')::text"
        else:
            query += " AND played_at >= datetime('now', '-7 days')"
    elif time_range == "ytd":
        if driver == "postgres":
            query += " AND played_at::timestamp >= (date_trunc('year', NOW()))::text"
        else:
            query += " AND played_at >= datetime('now', 'start of year')"

    query += f"""
    GROUP BY artist_name
    ORDER BY play_count DESC
    LIMIT {p}
    """

    cursor = conn.cursor()
    cursor.execute(query, (limit,))

    columns = [col[0] for col in cursor.description]
    results = [dict(zip(columns, row)) for row in cursor.fetchall()]

    conn.close()
    return results
