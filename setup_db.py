"""Initialize and set up the SQLite database for storing Spotify listening history.

This module creates the 'my_spotify_data.db' database with a 'listening_history'
table if they don't already exist.
"""

import sqlite3

from logging_config import configure_logger

logger = configure_logger(__name__)


def create_database():
    """Create the SQLite database and the listening_history table."""

    db_name = "my_spotify_data.db"

    logger.info("Connecting to database: %s...", db_name)

    try:
        conn = sqlite3.connect("my_spotify_data.db")
        cursor = conn.cursor()

        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS listening_history (
                played_at TEXT PRIMARY KEY,
                track_id TEXT,
                track_name TEXT,
                artist_name TEXT,
                album_name TEXT,
                album_image_url TEXT,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
            )
            """
        )

        logger.info("Table 'listening_history' checked/created successfully.")

        conn.commit()
        conn.close()
        logger.info("Database setup completed.")

    except sqlite3.Error as exc:
        logger.error("Database error occurred: %s", exc)


if __name__ == "__main__":
    create_database()
