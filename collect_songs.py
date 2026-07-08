"""Get data from spotify server using the user authentication and save it to the db"""

import time

from db_config import get_db_connection, get_placeholder
from authentication import auth_connection
from logging_config import configure_logger

logger = configure_logger(__name__)


def _batch_artist_meta(spotify_client, artist_ids):
    """Resolve Spotify artist id -> {"image_url": ..., "genres": ...}.

    Genres come from the same artists?ids= response as the images, so this
    costs no extra API calls. Genres are comma-joined; "" means the artist
    was fetched but Spotify lists no genres (vs NULL = never fetched).
    """
    meta = {}
    if not spotify_client or not artist_ids:
        return meta
    unique = list(dict.fromkeys(aid for aid in artist_ids if aid))
    for i in range(0, len(unique), 50):
        chunk = unique[i : i + 50]
        try:
            resp = spotify_client.artists(chunk)
            for artist in resp.get("artists") or []:
                if not artist:
                    continue
                images = artist.get("images") or []
                meta[artist["id"]] = {
                    "image_url": images[0]["url"] if images else None,
                    "genres": ", ".join(artist.get("genres") or []),
                }
        except Exception as exc:
            logger.warning("Batch artist meta fetch failed: %s", exc)
    return meta


def build_track_row(item, id_to_meta):
    """Flatten a Spotify recently-played item into a listening_history row.

    Returns values in insert order: (played_at, track_id, track_name,
    artist_name, album_name, album_image_url, artist_id, artist_image_url,
    duration_ms, artist_genres, album_release_date).
    """
    track = item["track"]
    album_images = track["album"].get("images") or []
    primary_artist = track.get("artists", [{}])[0]
    artist_id = primary_artist.get("id")
    meta = id_to_meta.get(artist_id) or {}
    return (
        item["played_at"],
        track["id"],
        track["name"],
        primary_artist.get("name"),
        track["album"]["name"],
        album_images[0]["url"] if album_images else None,
        artist_id,
        meta.get("image_url"),
        track.get("duration_ms"),
        meta.get("genres"),
        track["album"].get("release_date"),
    )


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
        sp = spotify_client or auth_connection()
        artist_ids_for_batch = []
        for item in tracks:
            primary = item["track"].get("artists", [{}])[0]
            aid = primary.get("id")
            if aid:
                artist_ids_for_batch.append(aid)
        id_to_meta = _batch_artist_meta(sp, artist_ids_for_batch)

        conn, driver = get_db_connection()
        if not conn:
            return

        cursor = conn.cursor()

        p = get_placeholder(driver)

        new_songs_count = 0

        columns = """(played_at, track_id, track_name, artist_name, album_name,
                 album_image_url, artist_id, artist_image_url, duration_ms,
                 artist_genres, album_release_date)"""
        values = f"VALUES ({p}, {p}, {p}, {p}, {p}, {p}, {p}, {p}, {p}, {p}, {p})"
        if driver == "postgres":
            sql = f"""
                INSERT INTO listening_history {columns}
                {values}
                ON CONFLICT (played_at) DO NOTHING
            """
        else:
            sql = f"""
                INSERT OR IGNORE INTO listening_history {columns}
                {values}
            """

        for item in tracks:
            track = item["track"]
            cursor.execute(sql, build_track_row(item, id_to_meta))

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

    sp = auth_connection()

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
