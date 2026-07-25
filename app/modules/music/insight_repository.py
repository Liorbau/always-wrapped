"""The five aggregate reads behind the dashboard's rotating insight card."""

from app.modules.music.repository import cursor_for, dict_rows, time_filter
from db.dialects import dialect_for


def most_played_songs(limit=30):
    with cursor_for() as (cursor, driver):
        cursor.execute(
            f"""
            SELECT track_name, artist_name, COUNT(*) as play_count
            FROM listening_history
            GROUP BY track_name, artist_name
            ORDER BY play_count DESC LIMIT {dialect_for(driver).placeholder}
            """,
            (limit,),
        )
        return dict_rows(cursor)


def most_played_artists(limit=30):
    with cursor_for() as (cursor, driver):
        cursor.execute(
            f"""
            SELECT artist_name, COUNT(*) as play_count
            FROM listening_history
            GROUP BY artist_name
            ORDER BY play_count DESC LIMIT {dialect_for(driver).placeholder}
            """,
            (limit,),
        )
        return dict_rows(cursor)


def recently_played_artist_names(limit=10):
    with cursor_for() as (cursor, driver):
        cursor.execute(
            f"""
            SELECT artist_name FROM listening_history
            WHERE 1=1 {time_filter(driver, "7days")}
            GROUP BY artist_name
            ORDER BY COUNT(*) DESC LIMIT {dialect_for(driver).placeholder}
            """,
            (limit,),
        )
        return {row[0] for row in cursor.fetchall()}


def peak_listening_hour(tz):
    with cursor_for() as (cursor, driver):
        hour_expr = dialect_for(driver).hour_of("played_at", tz)
        cursor.execute(
            f"""
            SELECT {hour_expr} as hour, COUNT(*) as cnt
            FROM listening_history
            GROUP BY hour ORDER BY cnt DESC LIMIT 1
            """
        )
        row = cursor.fetchone()
        return int(row[0]) if row and row[0] is not None else None


def library_totals():
    with cursor_for() as (cursor, _driver):
        cursor.execute(
            """
            SELECT COUNT(*) as total,
                   COUNT(DISTINCT track_name) as songs,
                   COUNT(DISTINCT artist_name) as artists
            FROM listening_history
            """
        )
        row = cursor.fetchone()
        if not row or not row[0]:
            return None
        return {"plays": row[0], "songs": row[1], "artists": row[2]}
