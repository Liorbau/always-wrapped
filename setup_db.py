"""Initialize and set up the SQLite database for storing Spotify listening history.

This module creates the 'my_spotify_data.db' database with a 'listening_history'
table if they don't already exist.
"""

from db_config import get_db_connection

from logging_config import configure_logger

logger = configure_logger(__name__)


def create_database():
    """Create the SQLite database and the listening_history table."""

    db_name = "my_spotify_data.db"

    logger.info("Connecting to database: %s...", db_name)

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
                timestamp {ts_type} DEFAULT CURRENT_TIMESTAMP
            )
            """
        )

        if driver == "postgres":
            cursor.execute(
                """
                SELECT column_name FROM information_schema.columns
                WHERE table_schema = 'public' AND table_name = 'listening_history'
                  AND column_name = 'artist_id'
                """
            )
            if not cursor.fetchone():
                cursor.execute(
                    "ALTER TABLE listening_history ADD COLUMN artist_id TEXT"
                )
        else:
            cursor.execute("PRAGMA table_info(listening_history)")
            col_names = [row[1] for row in cursor.fetchall()]
            if "artist_id" not in col_names:
                cursor.execute(
                    "ALTER TABLE listening_history ADD COLUMN artist_id TEXT"
                )

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
