"""Get data from spotify server using the user authentication and save it to the db"""

import sqlite3
import sys
import time

from dotenv import load_dotenv

from authentication import auth_connection
from logging_config import configure_logger

load_dotenv()

logger = configure_logger(__name__)


def get_spotify_client():
    """Retrieve an authenticated Spotify client.

    Returns:
        spotipy.Spotify: An authenticated Spotify client instance.
    """
    return auth_connection()


def fetch_recent_tracks(spotify_client, limit=50):
    """Fetch recently played tracks from Spotify.

    Args:
        spotify_client: The connected Spotify client.
        limit: Number of tracks to fetch (max 50).

    Returns:
        list: The 'items' list from the Spotify JSON response.
    """
    logger.info("Fetching last %d played tracks...", limit)

    results = spotify_client.current_user_recently_played(limit=limit)
    return results.get("items", [])


def save_tracks_to_db(tracks):
    """Parse the tracks and insert them into the database.

    Args:
        tracks: List of track items from Spotify API response.
    """
    if not tracks:
        logger.info("No tracks to save.")
        return

    db_name = "my_spotify_data.db"

    try:
        conn = sqlite3.connect(db_name)
        cursor = conn.cursor()

        new_songs_count = 0

        for item in tracks:
            track = item["track"]
            played_at = item["played_at"]

            if track["album"]["images"]:
                image_url = track["album"]["images"][0]["url"]
            else:
                image_url = None

            cursor.execute(
                """
                INSERT OR IGNORE INTO listening_history 
                (played_at, track_id, track_name, artist_name, album_name, album_image_url)
                VALUES (?, ?, ?, ?, ?, ?)
            """,
                (
                    played_at,
                    track["id"],
                    track["name"],
                    track["artists"][0]["name"],
                    track["album"]["name"],
                    image_url,
                ),
            )

            if cursor.rowcount > 0:
                new_songs_count += 1
                logger.info(
                    "New song saved: %s - %s",
                    track.get("name"),
                    track.get("artists", [{}])[0].get("name"),
                )

        conn.commit()
        conn.close()
        logger.info("Database update complete. Added %d new songs.", new_songs_count)

    except sqlite3.Error as exc:
        logger.error("Database error: %s", exc)


def start_collector_service():
    """Runs the collector loop 24/7."""
    logger.info("Starting Spotify Collector Service...")
    
    sp = get_spotify_client()
    
    if not sp:
        logger.error("Could not authenticate. Exiting collector.")
        return

    while True:
        try:
            logger.info("--- Starting Sync Cycle ---")
            recent_tracks = fetch_recent_tracks(sp)
            if recent_tracks:
                save_tracks_to_db(recent_tracks)
            else:
                logger.info("No tracks found or API error.")

            logger.info("Cycle complete. Sleeping for 20 minutes...")
            time.sleep(1200) # 20 minutes

        except Exception as exc:
            logger.error("Critical Error in loop: %s", exc)
            time.sleep(60)

if __name__ == "__main__":
    start_collector_service()