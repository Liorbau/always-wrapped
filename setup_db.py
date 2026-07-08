"""Initialize and set up the SQLite database for storing Spotify listening history.

This module creates the 'my_spotify_data.db' database with a 'listening_history'
table if they don't already exist.
"""

from db_config import get_db_connection

from logging_config import configure_logger

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
    """Create the listening_history table and run column migrations."""

    try:
        conn, driver = get_db_connection()
        if not conn:
            return

        cursor = conn.cursor()

        ts_type = "TIMESTAMP" if driver == "postgres" else "DATETIME"

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
                timestamp {ts_type} DEFAULT CURRENT_TIMESTAMP
            )
            """
        )

        if driver == "postgres":
            cursor.execute(
                """
                SELECT column_name FROM information_schema.columns
                WHERE table_schema = 'public' AND table_name = 'listening_history'
                """
            )
            existing = {row[0] for row in cursor.fetchall()}
        else:
            cursor.execute("PRAGMA table_info(listening_history)")
            existing = {row[1] for row in cursor.fetchall()}

        for col, col_type in MIGRATED_COLUMNS.items():
            if col not in existing:
                cursor.execute(
                    f"ALTER TABLE listening_history ADD COLUMN {col} {col_type}"
                )
                logger.info("Added missing column '%s' (%s).", col, col_type)

        logger.info(
            "Table 'listening_history' checked/created successfully on %s.",
            driver,
        )

        conn.commit()
        conn.close()
        logger.info("Database setup completed.")

    except Exception as exc:
        logger.error("Database error occurred: %s", exc)


if __name__ == "__main__":
    create_database()
