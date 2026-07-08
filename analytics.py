"""Data extraction and analysis from db."""

import html
import random

from db_config import get_db_connection, get_placeholder


def _time_filter(driver, time_range):
    """SQL predicate limiting played_at to the given range ('' = all time)."""
    if time_range == "7days":
        if driver == "postgres":
            return " AND played_at >= (NOW() - INTERVAL '7 days')::text"
        return " AND played_at >= datetime('now', '-7 days')"
    if time_range == "ytd":
        if driver == "postgres":
            return " AND played_at >= (date_trunc('year', NOW()))::text"
        return " AND played_at >= datetime('now', 'start of year')"
    return ""



def get_top_songs(limit=5, time_range="all_time"):
    """
    Returns the top listened songs, optionally filtered by time.
    time_range options: 'all_time', '7days', 'ytd'
    """
    conn, driver = get_db_connection()
    if not conn:
        return []
    p = get_placeholder(driver)

    query = """
    SELECT 
        track_name, 
        artist_name, 
        album_image_url, 
        COUNT(*) as play_count,
        MAX(track_id) as track_id
    FROM listening_history
    WHERE 1=1 
    """

    query += _time_filter(driver, time_range)

    query += f"""
    GROUP BY track_name, artist_name, album_image_url
    ORDER BY play_count DESC
    LIMIT {p}
    """

    cursor = conn.cursor()
    cursor.execute(query, (limit,))

    columns = [col[0] for col in cursor.description]
    results = [dict(zip(columns, row)) for row in cursor.fetchall()]

    conn.close()
    return results


def get_top_artists(limit=5, time_range="all_time"):
    """
    Returns the top artists, optionally filtered by time.
    """
    conn, driver = get_db_connection()
    if not conn:
        return []
    p = get_placeholder(driver)

    query = """
    SELECT 
        artist_name, 
        COUNT(*) as play_count,
        MAX(artist_image_url) as artist_image_url,
        MAX(artist_id) as artist_id
    FROM listening_history
    WHERE 1=1
    """

    query += _time_filter(driver, time_range)

    query += f"""
    GROUP BY artist_name
    ORDER BY play_count DESC
    LIMIT {p}
    """

    cursor = conn.cursor()
    cursor.execute(query, (limit,))

    columns = [col[0] for col in cursor.description]
    results = [dict(zip(columns, row)) for row in cursor.fetchall()]

    conn.close()
    return results


def get_random_insight():
    """Generate a random fun insight from listening data."""
    conn, driver = get_db_connection()
    if not conn:
        return {"text": "Start listening to get insights!", "icon": "lightbulb"}

    cursor = conn.cursor()
    insights = []

    try:
        # --- Insight: random song from top 30 ---
        cursor.execute(
            """
            SELECT track_name, artist_name, COUNT(*) as play_count
            FROM listening_history
            GROUP BY track_name, artist_name
            ORDER BY play_count DESC LIMIT 30
        """
        )
        songs = cursor.fetchall()
        if songs:
            i = random.randint(0, len(songs) - 1)
            insights.append(
                {
                    "text": f"<b>{html.escape(songs[i][0])}</b> by {html.escape(songs[i][1])} is your "
                    f"<b>#{i + 1}</b> most played song with {songs[i][2]} plays",
                    "icon": "music",
                }
            )

        # --- Insight: random artist from top 30 ---
        cursor.execute(
            """
            SELECT artist_name, COUNT(*) as play_count
            FROM listening_history
            GROUP BY artist_name
            ORDER BY play_count DESC LIMIT 30
        """
        )
        artists = cursor.fetchall()
        if artists:
            i = random.randint(0, len(artists) - 1)
            insights.append(
                {
                    "text": f"<b>{html.escape(artists[i][0])}</b> is your <b>#{i + 1}</b> "
                    f"most listened artist with {artists[i][1]} plays",
                    "icon": "microphone",
                }
            )

        # --- Insight: "miss you" — all-time top artist absent from last 7 days ---
        recent_filter = _time_filter(driver, "7days")

        cursor.execute(
            f"""
            SELECT artist_name FROM listening_history
            WHERE 1=1 {recent_filter}
            GROUP BY artist_name
            ORDER BY COUNT(*) DESC LIMIT 10
        """
        )
        recent_set = {row[0] for row in cursor.fetchall()}

        for idx, a in enumerate(artists[:10] if artists else []):
            if a[0] not in recent_set:
                msgs = [
                    f"<b>{html.escape(a[0])}</b> misses you! Your <b>#{idx + 1}</b> artist all time but nowhere this week",
                    f'Hey! <b>{html.escape(a[0])}</b> says: "Remember me? I\'m your <b>#{idx + 1}</b> artist!"',
                    f"<b>{html.escape(a[0])}</b> is feeling lonely — your <b>#{idx + 1}</b> all time but MIA this week",
                ]
                insights.append({"text": random.choice(msgs), "icon": "heart-crack"})
                break

        # --- Insight: peak listening hour ---
        if driver == "postgres":
            hour_expr = "EXTRACT(HOUR FROM played_at::timestamp)::int"
        else:
            hour_expr = "CAST(strftime('%H', played_at) AS INTEGER)"

        cursor.execute(
            f"""
            SELECT {hour_expr} as hour, COUNT(*) as cnt
            FROM listening_history
            GROUP BY hour ORDER BY cnt DESC LIMIT 1
        """
        )
        peak = cursor.fetchone()
        if peak:
            h = int(peak[0])
            if h >= 22 or h < 5:
                label = "a night owl"
            elif h < 9:
                label = "an early bird"
            elif h < 17:
                label = "a daytime listener"
            else:
                label = "an evening viber"
            insights.append(
                {
                    "text": f"You listen the most around <b>{h}:00</b> - you're {label}",
                    "icon": "clock",
                }
            )

        # --- Insight: total stats ---
        cursor.execute(
            """
            SELECT COUNT(*) as total,
                   COUNT(DISTINCT track_name) as songs,
                   COUNT(DISTINCT artist_name) as artists
            FROM listening_history
        """
        )
        stats = cursor.fetchone()
        if stats and stats[0] > 0:
            insights.append(
                {
                    "text": f"You've logged <b>{stats[0]}</b> plays across "
                    f"<b>{stats[1]}</b> unique songs from <b>{stats[2]}</b> artists",
                    "icon": "chart-bar",
                }
            )
    except Exception:
        pass

    conn.close()

    if not insights:
        return {"text": "Keep listening to unlock insights!", "icon": "lightbulb"}
    return random.choice(insights)


def search_music(query, time_range="all_time"):
    """Search for songs and artists by name or #rank number."""
    conn, driver = get_db_connection()
    if not conn:
        return []
    p = get_placeholder(driver)
    results = []

    time_filter = _time_filter(driver, time_range)

    cursor = conn.cursor()
    rank_str = query.strip().lstrip("#")
    is_rank = rank_str.isdigit()

    if is_rank:
        rank = int(rank_str)
        if rank < 1:
            conn.close()
            return []

        sql = f"""
            SELECT track_name, artist_name, album_image_url, COUNT(*) as play_count
            FROM listening_history WHERE 1=1 {time_filter}
            GROUP BY track_name, artist_name, album_image_url
            ORDER BY play_count DESC
            LIMIT 1 OFFSET {p}
        """
        cursor.execute(sql, (rank - 1,))
        cols = [c[0] for c in cursor.description]
        for row in cursor.fetchall():
            d = dict(zip(cols, row))
            d["type"] = "song"
            d["rank"] = rank
            results.append(d)

        sql = f"""
            SELECT artist_name, COUNT(*) as play_count
            FROM listening_history WHERE 1=1 {time_filter}
            GROUP BY artist_name
            ORDER BY play_count DESC
            LIMIT 1 OFFSET {p}
        """
        cursor.execute(sql, (rank - 1,))
        cols = [c[0] for c in cursor.description]
        for row in cursor.fetchall():
            d = dict(zip(cols, row))
            d["type"] = "artist"
            d["rank"] = rank
            results.append(d)
    else:
        search_lower = query.lower()

        sql = f"""
            SELECT track_name, artist_name, album_image_url, COUNT(*) as play_count
            FROM listening_history WHERE 1=1 {time_filter}
            GROUP BY track_name, artist_name, album_image_url
            ORDER BY play_count DESC
        """
        cursor.execute(sql)
        cols = [c[0] for c in cursor.description]
        song_matches = 0
        for i, row in enumerate(cursor.fetchall()):
            d = dict(zip(cols, row))
            if (
                search_lower in d["track_name"].lower()
                or search_lower in d["artist_name"].lower()
            ):
                d["type"] = "song"
                d["rank"] = i + 1
                results.append(d)
                song_matches += 1
                if song_matches >= 5:
                    break

        sql = f"""
            SELECT artist_name, COUNT(*) as play_count
            FROM listening_history WHERE 1=1 {time_filter}
            GROUP BY artist_name
            ORDER BY play_count DESC
        """
        cursor.execute(sql)
        cols = [c[0] for c in cursor.description]
        artist_matches = 0
        for i, row in enumerate(cursor.fetchall()):
            d = dict(zip(cols, row))
            if search_lower in d["artist_name"].lower():
                d["type"] = "artist"
                d["rank"] = i + 1
                results.append(d)
                artist_matches += 1
                if artist_matches >= 5:
                    break

    conn.close()
    return results
