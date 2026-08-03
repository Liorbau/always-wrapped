"""Durable shelf of DJ-pushed playlists and multi-criteria ratings.

Separate from hitl_decision (the Evaluator's approve/reject timeline). This is
the product surface for “Your DJ playlists” + star ratings (#10–#14).
"""

import hashlib
import json
import os
import re
import time

from agents.store import hitl
from db.connection import get_db_connection
from db.dialects import dialect_for
from db.rls import enable_rls
from core.logging import configure_logger

logger = configure_logger(__name__)

# Locked in epic #9 — API (#12) will edge-validate against this set.
CRITERIA = frozenset({
    "vibe_fit",
    "flow",
    "familiarity_vs_discovery",
    "occasion_fit",
    "overall",
})

_SPOTIFY_PLAYLIST_ID = re.compile(
    r"(?:open\.spotify\.com/playlist/|spotify:playlist:)([A-Za-z0-9]+)",
    re.IGNORECASE,
)


def ensure_tables(conn=None, driver=None):
    """Create both tables (idempotent). Caller closes conn if it opened one."""
    owns = conn is None
    if owns:
        conn, driver = get_db_connection()
        if conn is None:
            logger.error("Playlist tables not created: no DB connection.")
            return False
    try:
        _ensure(conn, driver)
        return True
    finally:
        if owns:
            conn.close()


def _ensure(conn, driver):
    cursor = conn.cursor()
    cursor.execute(
        """CREATE TABLE IF NOT EXISTS pushed_playlists (
            id TEXT PRIMARY KEY,
            spotify_playlist_id TEXT,
            url TEXT,
            name TEXT NOT NULL,
            description TEXT,
            tracks TEXT NOT NULL,
            context TEXT,
            pushed_at TEXT NOT NULL
        )"""
    )
    cursor.execute(
        """CREATE TABLE IF NOT EXISTS playlist_feedback (
            playlist_id TEXT NOT NULL,
            criterion TEXT NOT NULL,
            score REAL NOT NULL,
            note TEXT,
            rated_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            PRIMARY KEY (playlist_id, criterion)
        )"""
    )
    enable_rls(cursor, driver, "pushed_playlists")
    enable_rls(cursor, driver, "playlist_feedback")
    conn.commit()


def spotify_playlist_id_from_url(url):
    if not url:
        return None
    match = _SPOTIFY_PLAYLIST_ID.search(url)
    return match.group(1) if match else None


def context_from_playlist(playlist):
    """Compact non-track fields worth keeping for later Evaluator/UI context."""
    playlist = playlist or {}
    keys = (
        "familiarity_constraint", "target_duration_min",
        "artist_cap", "artist_cap_reason", "total_duration_min",
    )
    ctx = {k: playlist[k] for k in keys if playlist.get(k) not in (None, "")}
    return ctx or None


def upsert_pushed(
    record_id,
    playlist,
    url=None,
    pushed_at=None,
    spotify_playlist_id=None,
):
    """Insert or replace one pushed playlist. Idempotent on `record_id`."""
    if not record_id:
        return False
    playlist = playlist or {}
    conn, driver = get_db_connection()
    if conn is None:
        logger.error("Pushed playlist not recorded (no DB): %s", playlist.get("name"))
        return False

    try:
        _ensure(conn, driver)
        p = dialect_for(driver).placeholder
        cursor = conn.cursor()
        url = url or ""
        sid = spotify_playlist_id or spotify_playlist_id_from_url(url)
        name = playlist.get("name") or "Untitled"
        description = playlist.get("description") or ""
        tracks = json.dumps(playlist.get("tracks") or [], ensure_ascii=False)
        context = context_from_playlist(playlist)
        context_json = json.dumps(context, ensure_ascii=False) if context else None
        at = pushed_at or time.strftime("%Y-%m-%dT%H:%M:%S")

        cursor.execute(
            f"UPDATE pushed_playlists SET spotify_playlist_id = {p}, url = {p}, "
            f"name = {p}, description = {p}, tracks = {p}, context = {p}, "
            f"pushed_at = {p} WHERE id = {p}",
            (sid, url, name, description, tracks, context_json, at, record_id),
        )
        if cursor.rowcount == 0:
            cursor.execute(
                "INSERT INTO pushed_playlists "
                "(id, spotify_playlist_id, url, name, description, tracks, context, pushed_at) "
                f"VALUES ({p}, {p}, {p}, {p}, {p}, {p}, {p}, {p})",
                (record_id, sid, url, name, description, tracks, context_json, at),
            )
        conn.commit()
        return True
    finally:
        conn.close()


def upsert_feedback(playlist_id, criterion, score, note=None):
    """Upsert one criterion score (0–5). Returns False on bad input / no DB."""
    if not playlist_id or criterion not in CRITERIA:
        return False
    try:
        score = float(score)
    except (TypeError, ValueError):
        return False
    if score < 0 or score > 5:
        return False

    conn, driver = get_db_connection()
    if conn is None:
        logger.error("Playlist feedback not recorded (no DB): %s", playlist_id)
        return False

    try:
        _ensure(conn, driver)
        dialect = dialect_for(driver)
        now = time.strftime("%Y-%m-%dT%H:%M:%S")
        cursor = conn.cursor()
        p = dialect.placeholder
        cursor.execute(
            f"SELECT rated_at, note FROM playlist_feedback "
            f"WHERE playlist_id = {p} AND criterion = {p}",
            (playlist_id, criterion),
        )
        row = cursor.fetchone()
        if row:
            rated_at = row[0]
            # None = leave note unchanged; "" clears it.
            if note is None:
                note = row[1]
            else:
                note = note.strip() or None
        else:
            rated_at = now
            note = (note or "").strip() or None
        cursor.execute(
            dialect.upsert(
                "playlist_feedback",
                ["playlist_id", "criterion", "score", "note", "rated_at", "updated_at"],
                conflict="playlist_id, criterion",
                updates=["score", "note", "updated_at"],
            ),
            (playlist_id, criterion, score, note, rated_at, now),
        )
        conn.commit()
        return True
    finally:
        conn.close()


def list_pushed(limit=50):
    """Newest first. Empty list if the ledger is unreachable."""
    conn, driver = get_db_connection()
    if conn is None:
        logger.error("Pushed playlists unavailable: no DB connection.")
        return []

    try:
        _ensure(conn, driver)
        p = dialect_for(driver).placeholder
        cursor = conn.cursor()
        cursor.execute(
            "SELECT id, spotify_playlist_id, url, name, description, tracks, "
            "context, pushed_at FROM pushed_playlists "
            f"ORDER BY pushed_at DESC LIMIT {p}",
            (int(limit),),
        )
        return [_row_to_playlist(row) for row in cursor.fetchall()]
    finally:
        conn.close()


def feedback_for(playlist_id):
    """All criterion rows for one playlist (empty if none / unread)."""
    conn, driver = get_db_connection()
    if conn is None:
        return []

    try:
        _ensure(conn, driver)
        p = dialect_for(driver).placeholder
        cursor = conn.cursor()
        cursor.execute(
            "SELECT criterion, score, note, rated_at, updated_at "
            f"FROM playlist_feedback WHERE playlist_id = {p} ORDER BY criterion",
            (playlist_id,),
        )
        return [
            {
                "criterion": row[0],
                "score": float(row[1]),
                "note": row[2],
                "rated_at": row[3],
                "updated_at": row[4],
            }
            for row in cursor.fetchall()
        ]
    finally:
        conn.close()


def _row_to_playlist(row):
    try:
        tracks = json.loads(row[5] or "[]")
    except (TypeError, ValueError):
        tracks = []
    try:
        context = json.loads(row[6]) if row[6] else None
    except (TypeError, ValueError):
        context = None
    return {
        "id": row[0],
        "spotify_playlist_id": row[1],
        "url": row[2],
        "name": row[3],
        "description": row[4],
        "tracks": tracks,
        "context": context,
        "pushed_at": row[7],
    }


def import_from_hitl():
    """Upsert every pushed HITL decision. Returns how many rows were written."""
    conn, driver = get_db_connection()
    if conn is None:
        logger.error("HITL → pushed_playlists import skipped: no DB.")
        return 0

    try:
        hitl._ensure_table(conn)
        p = dialect_for(driver).placeholder
        cursor = conn.cursor()
        cursor.execute(
            "SELECT id, ts, playlist_url, playlist FROM hitl_decision "
            f"WHERE decision = {p} ORDER BY ts ASC",
            (hitl.PUSHED,),
        )
        rows = cursor.fetchall()
    finally:
        conn.close()

    imported = 0
    for record_id, ts, url, playlist_json in rows:
        try:
            playlist = json.loads(playlist_json) if playlist_json else {}
        except (TypeError, ValueError):
            logger.warning("Skipping hitl push %s: bad playlist JSON", record_id)
            continue
        if upsert_pushed(record_id, playlist, url=url, pushed_at=ts):
            imported += 1
    return imported


def import_from_jsonl(directory):
    """Upsert legacy pushes.jsonl lines. Returns how many rows were written."""
    path = os.path.join(directory, "pushes.jsonl")
    if not os.path.isfile(path):
        return 0

    imported = 0
    with open(path) as handle:
        for line in handle:
            if not line.strip():
                continue
            try:
                entry = json.loads(line)
            except ValueError:
                logger.warning("Skipping malformed line in %s", path)
                continue
            record_id = hashlib.sha1(line.strip().encode()).hexdigest()
            if upsert_pushed(
                record_id,
                entry.get("playlist") or {},
                url=entry.get("url"),
                pushed_at=entry.get("ts"),
            ):
                imported += 1
    return imported
