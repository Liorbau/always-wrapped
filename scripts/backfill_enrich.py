"""One-off backfill for historical rows: artist_genres and duration_ms.

Only fills NULLs, never overwrites — safe to re-run and safe to interrupt.
Run from the repo root with the same env as the collector (DATABASE_URL for
Postgres, Spotify keys in .env):

    python scripts/backfill_enrich.py
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from integrations.spotify import auth_connection
from db.connection import get_db_connection
from db.dialects import dialect_for
from core.logging import configure_logger
from db.schema import create_database

logger = configure_logger(__name__)

BATCH = 50  # max ids per Spotify artists/tracks request


def _chunks(seq, size=BATCH):
    for i in range(0, len(seq), size):
        yield seq[i : i + size]


def backfill_artist_ids(sp, conn, driver):
    """Recover artist_id for legacy rows (pre-artist_id schema) via track_id."""
    p = dialect_for(driver).placeholder
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT DISTINCT track_id FROM listening_history
        WHERE track_id IS NOT NULL AND artist_id IS NULL
        """
    )
    track_ids = [row[0] for row in cursor.fetchall()]
    logger.info("Artist ids: %d legacy tracks to resolve.", len(track_ids))

    updated = 0
    for chunk in _chunks(track_ids):
        resp = sp.tracks(chunk)
        for track in resp.get("tracks") or []:
            if not track:
                continue
            primary = (track.get("artists") or [{}])[0]
            if not primary.get("id"):
                continue
            cursor.execute(
                f"""
                UPDATE listening_history SET artist_id = {p}
                WHERE track_id = {p} AND artist_id IS NULL
                """,
                (primary["id"], track["id"]),
            )
            updated += cursor.rowcount
        conn.commit()
        logger.info("Artist ids: committed batch, %d rows updated so far.", updated)
    return updated


def backfill_genres(sp, conn, driver):
    """Fill artist_genres for every artist_id that has never been fetched."""
    p = dialect_for(driver).placeholder
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT DISTINCT artist_id FROM listening_history
        WHERE artist_id IS NOT NULL AND artist_genres IS NULL
        """
    )
    artist_ids = [row[0] for row in cursor.fetchall()]
    logger.info("Genres: %d artists to fetch.", len(artist_ids))

    updated = 0
    for chunk in _chunks(artist_ids):
        resp = sp.artists(chunk)
        for artist in resp.get("artists") or []:
            if not artist:
                continue
            # "" = fetched but Spotify lists no genres (vs NULL = never fetched)
            genres = ", ".join(artist.get("genres") or [])
            cursor.execute(
                f"""
                UPDATE listening_history SET artist_genres = {p}
                WHERE artist_id = {p} AND artist_genres IS NULL
                """,
                (genres, artist["id"]),
            )
            updated += cursor.rowcount
        conn.commit()
        logger.info("Genres: committed batch, %d rows updated so far.", updated)
    return updated


def backfill_durations(sp, conn, driver):
    """Fill duration_ms for every track_id missing it."""
    p = dialect_for(driver).placeholder
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT DISTINCT track_id FROM listening_history
        WHERE track_id IS NOT NULL AND duration_ms IS NULL
        """
    )
    track_ids = [row[0] for row in cursor.fetchall()]
    logger.info("Durations: %d tracks to fetch.", len(track_ids))

    updated = 0
    for chunk in _chunks(track_ids):
        resp = sp.tracks(chunk)
        for track in resp.get("tracks") or []:
            if not track or track.get("duration_ms") is None:
                continue
            cursor.execute(
                f"""
                UPDATE listening_history SET duration_ms = {p}
                WHERE track_id = {p} AND duration_ms IS NULL
                """,
                (track["duration_ms"], track["id"]),
            )
            updated += cursor.rowcount
        conn.commit()
        logger.info("Durations: committed batch, %d rows updated so far.", updated)
    return updated


def backfill_release_dates(sp, conn, driver):
    """Fill album_release_date for every track_id missing it."""
    p = dialect_for(driver).placeholder
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT DISTINCT track_id FROM listening_history
        WHERE track_id IS NOT NULL AND album_release_date IS NULL
        """
    )
    track_ids = [row[0] for row in cursor.fetchall()]
    logger.info("Release dates: %d tracks to fetch.", len(track_ids))

    updated = 0
    for chunk in _chunks(track_ids):
        resp = sp.tracks(chunk)
        for track in resp.get("tracks") or []:
            date = ((track or {}).get("album") or {}).get("release_date")
            if not track or not date:
                continue
            cursor.execute(
                f"""
                UPDATE listening_history SET album_release_date = {p}
                WHERE track_id = {p} AND album_release_date IS NULL
                """,
                (date, track["id"]),
            )
            updated += cursor.rowcount
        conn.commit()
        logger.info("Release dates: committed batch, %d rows updated so far.", updated)
    return updated


def main():
    sp = auth_connection()
    if not sp:
        logger.error("Spotify auth failed. Aborting.")
        sys.exit(1)

    create_database()  # ensure the new columns exist before backfilling

    conn, driver = get_db_connection()
    if not conn:
        logger.error("DB connection failed. Aborting.")
        sys.exit(1)
    logger.info("Backfilling on driver: %s", driver)

    artist_ids = backfill_artist_ids(sp, conn, driver)
    genres = backfill_genres(sp, conn, driver)
    durations = backfill_durations(sp, conn, driver)
    release_dates = backfill_release_dates(sp, conn, driver)

    conn.close()
    logger.info(
        "Done. Rows updated — artist_ids: %d, genres: %d, durations: %d, release_dates: %d.",
        artist_ids,
        genres,
        durations,
        release_dates,
    )


if __name__ == "__main__":
    main()
