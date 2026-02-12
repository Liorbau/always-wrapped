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
                timestamp {ts_type} DEFAULT CURRENT_TIMESTAMP
            )
            """
        )

        logger.info(
            "Table 'listening_history' checked/created successfully on %s.", driver,
        )

        conn.commit()
        conn.close()
        logger.info("Database setup completed.")

    except Exception as exc:
        logger.error("Database error occurred: %s", exc)


if __name__ == "__main__":
    create_database()
