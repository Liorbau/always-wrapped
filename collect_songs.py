"""Get data from spotify server using the user authentication and save it to the db"""

import time

from dotenv import load_dotenv

from db_config import get_db_connection, get_placeholder
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


def _batch_artist_image_urls(spotify_client, artist_ids):
    """Resolve Spotify artist id -> profile image URL (largest image)."""
    urls = {}
    if not spotify_client or not artist_ids:
        return urls
    unique = list(dict.fromkeys(aid for aid in artist_ids if aid))
    for i in range(0, len(unique), 50):
        chunk = unique[i : i + 50]
        try:
            resp = spotify_client.artists(chunk)
            for artist in resp.get("artists") or []:
                if not artist:
                    continue
                images = artist.get("images") or []
                urls[artist["id"]] = images[0]["url"] if images else None
        except Exception as exc:
            logger.warning("Batch artist image fetch failed: %s", exc)
    return urls


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


def save_tracks_to_db(tracks, spotify_client=None):
    """Parse the tracks and insert them into the database.

    Args:
        tracks: List of track items from Spotify API response.
        spotify_client: Optional authenticated client used to batch-fetch artist
            profile images (one artists?ids= request per up to 50 unique ids).
    """
    if not tracks:
        logger.info("No tracks to save.")
        return

    try:
        sp = spotify_client or get_spotify_client()
        artist_ids_for_batch = []
        for item in tracks:
            primary = item["track"].get("artists", [{}])[0]
            aid = primary.get("id")
            if aid:
                artist_ids_for_batch.append(aid)
        id_to_artist_img = _batch_artist_image_urls(sp, artist_ids_for_batch)

        conn, driver = get_db_connection()
        if not conn:
            return

        cursor = conn.cursor()

        p = get_placeholder(driver)

        new_songs_count = 0

        for item in tracks:
            track = item["track"]
            played_at = item["played_at"]

            if track["album"]["images"]:
                image_url = track["album"]["images"][0]["url"]
            else:
                image_url = None

            primary_artist = track.get("artists", [{}])[0]
            artist_spotify_id = primary_artist.get("id")
            artist_img_url = (
                id_to_artist_img.get(artist_spotify_id) if artist_spotify_id else None
            )

            if driver == "postgres":
                sql = f"""
                    INSERT INTO listening_history 
                    (played_at, track_id, track_name, artist_name, album_name,
                     album_image_url, artist_id, artist_image_url)
                    VALUES ({p}, {p}, {p}, {p}, {p}, {p}, {p}, {p})
                    ON CONFLICT (played_at) DO NOTHING
                """
            else:
                sql = f"""
                INSERT OR IGNORE INTO listening_history 
                (played_at, track_id, track_name, artist_name, album_name,
                 album_image_url, artist_id, artist_image_url)
                VALUES ({p}, {p}, {p}, {p}, {p}, {p}, {p}, {p})
                """

            cursor.execute(
                sql,
                (
                    played_at,
                    track["id"],
                    track["name"],
                    primary_artist.get("name"),
                    track["album"]["name"],
                    image_url,
                    artist_spotify_id,
                    artist_img_url,
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

    except Exception as exc:
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
                save_tracks_to_db(recent_tracks, sp)
            else:
                logger.info("No tracks found or API error.")

            logger.info("Cycle complete. Sleeping for 20 minutes...")
            time.sleep(1200)  # 20 minutes

        except Exception as exc:
            logger.error("Critical Error in loop: %s", exc)
            time.sleep(60)


if __name__ == "__main__":
    start_collector_service()
