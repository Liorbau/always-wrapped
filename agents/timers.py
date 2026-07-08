"""Standing playlist timers: "every Sun-Thu at 07:30, a ~50-min train playlist".

Created over Telegram commands (/timer), stored in the playlist_timers table,
and checked once a minute by a background loop. A firing timer runs the DJ and
sends the usual Approve/Reject proposal — the scheduled path never writes to
the Spotify account; the push still waits for the user's tap (HITL).
"""

import datetime
import os
import time

from db_config import get_db_connection, get_placeholder
from logging_config import configure_logger

logger = configure_logger(__name__)

DAYS = ("mon", "tue", "wed", "thu", "fri", "sat", "sun")
GRACE_MIN = 60  # fire up to an hour late (e.g. server restart), never later
COLS = ("id", "at_hhmm", "days", "prompt", "chat_id", "last_fired")

USAGE = ("Usage: /timer HH:MM <days> <what you want>\n"
         "e.g. /timer 07:30 sun-thu a 50-minute upbeat playlist for my train\n"
         "days: daily, a range like sun-thu, or a list like mon,wed,fri\n"
         "/timers — list active timers\n"
         "/deltimer <id> — remove one\n"
         "/plan — build playlists for tomorrow from your calendar")


def user_now():
    """Now in the user's timezone (USER_TZ env, default Asia/Jerusalem)."""
    try:
        from zoneinfo import ZoneInfo
        return datetime.datetime.now(ZoneInfo(os.getenv("USER_TZ", "Asia/Jerusalem")))
    except Exception:  # tz database missing — fall back to server time
        return datetime.datetime.now()


def expand_days(token):
    """'daily' | 'sun-thu' (may wrap the week) | 'mon,wed' -> day list, or None."""
    token = token.lower()
    if token == "daily":
        return list(DAYS)
    if "-" in token:
        a, _, b = token.partition("-")
        if a[:3] in DAYS and b[:3] in DAYS:
            i, j = DAYS.index(a[:3]), DAYS.index(b[:3])
            return [DAYS[k % 7] for k in range(i, i + (j - i) % 7 + 1)]
        return None
    parts = [p.strip()[:3] for p in token.split(",") if p.strip()]
    return parts if parts and all(p in DAYS for p in parts) else None


def parse_timer(text):
    """'/timer 07:30 sun-thu a 50-min ...' -> {at, days, prompt} or {'error'}."""
    parts = text.split(None, 3)
    if len(parts) < 4:
        return {"error": USAGE}
    _, at, days_token, prompt = parts
    try:
        at = datetime.datetime.strptime(at, "%H:%M").strftime("%H:%M")
    except ValueError:
        return {"error": f"Bad time '{at}' — use HH:MM.\n\n{USAGE}"}
    days = expand_days(days_token)
    if not days:
        return {"error": f"Bad days '{days_token}'.\n\n{USAGE}"}
    return {"at": at, "days": days, "prompt": prompt.strip()}


def _conn():
    conn, driver = get_db_connection()
    if conn is None:
        raise RuntimeError("No database connection.")
    id_col = ("SERIAL PRIMARY KEY" if driver == "postgres"
              else "INTEGER PRIMARY KEY AUTOINCREMENT")
    conn.cursor().execute(f"""CREATE TABLE IF NOT EXISTS playlist_timers (
        id {id_col},
        at_hhmm TEXT NOT NULL,
        days TEXT NOT NULL,
        prompt TEXT NOT NULL,
        chat_id TEXT NOT NULL,
        last_fired TEXT)""")
    conn.commit()
    return conn, driver


def add_timer(at, days, prompt, chat_id):
    conn, driver = _conn()
    ph = get_placeholder(driver)
    cur = conn.cursor()
    cur.execute(f"INSERT INTO playlist_timers (at_hhmm, days, prompt, chat_id) "
                f"VALUES ({ph}, {ph}, {ph}, {ph})" +
                (" RETURNING id" if driver == "postgres" else ""),
                (at, ",".join(days), prompt, str(chat_id)))
    timer_id = cur.fetchone()[0] if driver == "postgres" else cur.lastrowid
    conn.commit()
    conn.close()
    return timer_id


def list_timers():
    conn, _ = _conn()
    cur = conn.cursor()
    cur.execute(f"SELECT {', '.join(COLS)} FROM playlist_timers ORDER BY id")
    rows = [dict(zip(COLS, r)) for r in cur.fetchall()]
    conn.close()
    return rows


def delete_timer(timer_id):
    conn, driver = _conn()
    cur = conn.cursor()
    cur.execute(f"DELETE FROM playlist_timers WHERE id = {get_placeholder(driver)}",
                (timer_id,))
    conn.commit()
    gone = cur.rowcount > 0
    conn.close()
    return gone


def mark_fired(timer_id, day):
    conn, driver = _conn()
    ph = get_placeholder(driver)
    conn.cursor().execute(
        f"UPDATE playlist_timers SET last_fired = {ph} WHERE id = {ph}",
        (day, timer_id))
    conn.commit()
    conn.close()


def due_timers(now=None):
    """Timers that should fire: right day, within GRACE_MIN after their time,
    not already fired today."""
    now = now or user_now()
    today, dow = now.strftime("%Y-%m-%d"), DAYS[now.weekday()]
    mins = now.hour * 60 + now.minute
    due = []
    for t in list_timers():
        h, m = t["at_hhmm"].split(":")
        if (dow in t["days"].split(",")
                and 0 <= mins - (int(h) * 60 + int(m)) < GRACE_MIN
                and t["last_fired"] != today):
            due.append(t)
    return due


def handle_command(text, chat_id):
    """A /command from the (verified) Telegram chat -> reply text."""
    cmd = text.split(None, 1)[0].split("@")[0].lower()
    if cmd == "/timers":
        rows = list_timers()
        return ("\n".join(f"#{t['id']} {t['days']} at {t['at_hhmm']} — {t['prompt']}"
                          for t in rows) or "No timers set.\n\n" + USAGE)
    if cmd == "/deltimer":
        arg = text.split(None, 2)[1:2]
        if not (arg and arg[0].isdigit()):
            return "Usage: /deltimer <id> (see /timers)"
        return (f"Timer #{arg[0]} removed." if delete_timer(int(arg[0]))
                else f"No timer #{arg[0]}.")
    if cmd == "/timer":
        parsed = parse_timer(text)
        if "error" in parsed:
            return parsed["error"]
        timer_id = add_timer(parsed["at"], parsed["days"], parsed["prompt"], chat_id)
        return (f"⏰ Timer #{timer_id} set: {','.join(parsed['days'])} at "
                f"{parsed['at']} — {parsed['prompt']}\n"
                "I'll build it and send it here for your approval.")
    return USAGE  # /start, /help, anything else


def daily_due(hhmm, now, last_date):
    """True if a once-a-day task should fire now: within GRACE_MIN after its
    time and not already fired today (same window logic as timers)."""
    h, m = hhmm.split(":")
    mins = now.hour * 60 + now.minute
    return (now.strftime("%Y-%m-%d") != last_date
            and 0 <= mins - (int(h) * 60 + int(m)) < GRACE_MIN)


def start_timer_service(fire, daily=None, poll_s=60):
    """Blocking loop for a daemon thread; fire(row) builds + proposes.

    daily=(hhmm, callback) also fires callback() once a day at hhmm (used for
    the nightly Planner run).
    """
    logger.info("Timer service started (poll every %ss).", poll_s)
    last_daily = None
    while True:
        try:
            for row in due_timers():
                # mark BEFORE firing: a crashing DJ run must not retry all day
                mark_fired(row["id"], user_now().strftime("%Y-%m-%d"))
                fire(row)
            if daily:
                hhmm, cb = daily
                now = user_now()
                if daily_due(hhmm, now, last_daily):
                    last_daily = now.strftime("%Y-%m-%d")
                    logger.info("Daily task firing at %s.", hhmm)
                    cb()
        except Exception:
            logger.exception("Timer tick failed.")
        time.sleep(poll_s)
