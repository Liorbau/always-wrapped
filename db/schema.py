"""Initialize and set up the SQLite database for storing Spotify listening history.

This module creates the 'my_spotify_data.db' database with a 'listening_history'
table if they don't already exist.
"""

from db.connection import get_db_connection
from db.dialects import dialect_for

from core.logging import configure_logger

logger = configure_logger(__name__)

# Columns added after the initial schema; migrated in-place on startup.
MIGRATED_COLUMNS = {
    "artist_id": "TEXT",
    "artist_image_url": "TEXT",
    "duration_ms": "INTEGER",
    "artist_genres": "TEXT",
    "album_release_date": "TEXT",
}


def create_database():
    """Create the listening_history table and run column migrations.

    Raises on a schema failure: booting with a half-migrated table is worse
    than not booting, and this used to be swallowed into a log line.
    """
    conn, driver = get_db_connection()
    if conn is None:
        logger.error("Schema setup skipped: no database connection.")
        return

    try:
        cursor = conn.cursor()

        dialect = dialect_for(driver)

        cursor.execute(
            f"""
            CREATE TABLE IF NOT EXISTS listening_history (
                played_at TEXT PRIMARY KEY,
                track_id TEXT,
                track_name TEXT,
                artist_name TEXT,
                album_name TEXT,
                album_image_url TEXT,
                artist_id TEXT,
                artist_image_url TEXT,
                duration_ms INTEGER,
                artist_genres TEXT,
                timestamp {dialect.timestamp_type} DEFAULT CURRENT_TIMESTAMP
            )
            """
        )

        existing = dialect.existing_columns(cursor, "listening_history")

        for col, col_type in MIGRATED_COLUMNS.items():
            if col not in existing:
                cursor.execute(
                    f"ALTER TABLE listening_history ADD COLUMN {col} {col_type}"
                )
                logger.info("Added missing column '%s' (%s).", col, col_type)

        conn.commit()
        logger.info("Schema ready on %s.", driver)
    except Exception:
        logger.exception("Schema setup failed on %s.", driver)
        raise
    finally:
        conn.close()


if __name__ == "__main__":
    create_database()
