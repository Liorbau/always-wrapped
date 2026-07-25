"""Persistence for `listening_history`: SQL in, plain rows out.

No HTTP, no Spotify, no presentation. Every query is driver-branched because
prod runs Postgres and local runs SQLite.
"""

from contextlib import contextmanager

from app.errors import AppError, INTERNAL_ERROR
from db.connection import get_db_connection
from db.dialects import dialect_for


@contextmanager
def cursor_for(readonly=False):
    conn, driver = get_db_connection(readonly=readonly)
    if conn is None:
        raise AppError(INTERNAL_ERROR, "Database connection failed.")
    try:
        yield conn.cursor(), driver
    finally:
        conn.close()


def dict_rows(cursor):
    columns = [col[0] for col in cursor.description]
    return [dict(zip(columns, row)) for row in cursor.fetchall()]


RECENT_DAYS = 7


def time_filter(driver, time_range):
    """SQL predicate limiting played_at to the given range ('' = all time)."""
    dialect = dialect_for(driver)
    if time_range == "7days":
        return " AND " + dialect.within_last_days("played_at", RECENT_DAYS)
    if time_range == "ytd":
        return " AND " + dialect.since_start_of_year("played_at")
    return ""


def recent_plays(limit=50):
    with cursor_for() as (cursor, driver):
        cursor.execute(
            f"SELECT * FROM listening_history ORDER BY played_at DESC "
            f"LIMIT {dialect_for(driver).placeholder}",
            (limit,),
        )
        return dict_rows(cursor)


def top_songs(limit=5, time_range="all_time"):
    with cursor_for() as (cursor, driver):
        cursor.execute(
            f"""
            SELECT track_name, artist_name, album_image_url,
                   COUNT(*) as play_count, MAX(track_id) as track_id
            FROM listening_history
            WHERE 1=1 {time_filter(driver, time_range)}
            GROUP BY track_name, artist_name, album_image_url
            ORDER BY play_count DESC
            LIMIT {dialect_for(driver).placeholder}
            """,
            (limit,),
        )
        return dict_rows(cursor)


def top_artists(limit=5, time_range="all_time"):
    with cursor_for() as (cursor, driver):
        cursor.execute(
            f"""
            SELECT artist_name, COUNT(*) as play_count,
                   MAX(artist_image_url) as artist_image_url,
                   MAX(artist_id) as artist_id
            FROM listening_history
            WHERE 1=1 {time_filter(driver, time_range)}
            GROUP BY artist_name
            ORDER BY play_count DESC
            LIMIT {dialect_for(driver).placeholder}
            """,
            (limit,),
        )
        return dict_rows(cursor)


def songs_by_rank(time_range="all_time", offset=None):
    """Play-count-ordered songs. `offset` returns exactly the row at that rank."""
    with cursor_for() as (cursor, driver):
        sql = f"""
            SELECT track_name, artist_name, album_image_url, COUNT(*) as play_count
            FROM listening_history
            WHERE 1=1 {time_filter(driver, time_range)}
            GROUP BY track_name, artist_name, album_image_url
            ORDER BY play_count DESC
        """
        if offset is None:
            cursor.execute(sql)
        else:
            cursor.execute(f"{sql} LIMIT 1 OFFSET {dialect_for(driver).placeholder}", (offset,))
        return dict_rows(cursor)


def artists_by_rank(time_range="all_time", offset=None):
    with cursor_for() as (cursor, driver):
        sql = f"""
            SELECT artist_name, COUNT(*) as play_count
            FROM listening_history
            WHERE 1=1 {time_filter(driver, time_range)}
            GROUP BY artist_name
            ORDER BY play_count DESC
        """
        if offset is None:
            cursor.execute(sql)
        else:
            cursor.execute(f"{sql} LIMIT 1 OFFSET {dialect_for(driver).placeholder}", (offset,))
        return dict_rows(cursor)
