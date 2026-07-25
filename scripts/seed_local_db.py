"""Fill a local SQLite database with plausible listening history.

Lets you run the whole app locally — dashboard, search, insights, Wrapped —
without pointing at the production database.

    DATABASE_URL= ./venv/bin/python scripts/seed_local_db.py [--days 90] [--reset]

DATABASE_URL must be set to empty so db.connection chooses SQLite; an unset
variable is refilled from .env, which points at production.
"""

import os
import random
import sys
from datetime import datetime, timedelta, timezone

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.logging import configure_logger
from db.connection import get_db_connection
from db.dialects import dialect_for
from db.schema import create_database
from pipelines.collector import TRACK_COLUMNS

logger = configure_logger(__name__)

DEFAULT_DAYS = 90
PLAYS_PER_DAY = (8, 26)

# Any non-empty URL keeps the dashboard from calling Spotify to backfill art.
# These 404 in the browser and fall back to the local icon, which is fine.
PLACEHOLDER_ART = "https://local.invalid/art"

# (artist, genres, decade of release) -> a few tracks each
CATALOG = [
    ("Radiohead", "alternative rock, art rock", "1997",
     ["Paranoid Android", "Karma Police", "No Surprises", "Let Down"]),
    ("Kendrick Lamar", "hip hop, west coast rap", "2015",
     ["Alright", "King Kunta", "Money Trees", "Swimming Pools"]),
    ("Berry Sakharof", "israeli rock, mizrahi", "2013",
     ["Ha'Yalda Hachi Yafa", "Erev Kachol Amok", "Simanim Shel Chulsha"]),
    ("Fleetwood Mac", "classic rock, soft rock", "1977",
     ["Dreams", "Go Your Own Way", "The Chain", "Everywhere"]),
    ("Bonobo", "downtempo, electronic", "2017",
     ["Kerala", "Break Apart", "Bambro Koyo Ganda"]),
    ("Idan Raichel", "israeli, world", "2005",
     ["Mimaamakim", "Bo'ee", "Im Telech"]),
    ("Daft Punk", "french house, electronic", "2001",
     ["Digital Love", "One More Time", "Something About Us"]),
    ("Nina Simone", "jazz, soul", "1965",
     ["Feeling Good", "Sinnerman", "I Put A Spell On You"]),
]


def build_rows(days, rng):
    """One row per play, walking backwards from now with a realistic day shape."""
    rows = []
    now = datetime.now(timezone.utc).replace(minute=0, second=0, microsecond=0)

    for day_offset in range(days):
        day = now - timedelta(days=day_offset)
        for _ in range(rng.randint(*PLAYS_PER_DAY)):
            artist, genres, year, tracks = rng.choice(CATALOG)
            title = rng.choice(tracks)
            # people listen in the morning, at lunch, and in the evening
            hour = rng.choice([7, 8, 9, 12, 13, 16, 17, 18, 19, 20, 21, 22])
            played = day.replace(hour=hour, minute=rng.randint(0, 59),
                                 second=rng.randint(0, 59))
            duration = rng.randint(150, 320) * 1000
            slug = f"{artist[:3]}{abs(hash(title)) % 10**6}".lower()
            artist_id = f"a{artist.lower().replace(' ', '')[:8]}"
            # Artwork URLs are filled in on purpose: a row with a missing
            # artist image sends the dashboard to Spotify to backfill it, which
            # would make local runs depend on the network.
            rows.append((
                played.strftime("%Y-%m-%dT%H:%M:%S.000Z"),
                f"t{slug}", title, artist, f"{title} — Single",
                f"{PLACEHOLDER_ART}/album/{slug}", artist_id,
                f"{PLACEHOLDER_ART}/artist/{artist_id}",
                duration, genres, year,
            ))
    return rows


def seed(days, reset):
    create_database()
    conn, driver = get_db_connection()
    if conn is None:
        print("No database connection. Did you run with DATABASE_URL= ?")
        return 0

    dialect = dialect_for(driver)
    cursor = conn.cursor()
    if reset:
        cursor.execute("DELETE FROM listening_history")
        print("  cleared existing rows")

    rows = build_rows(days, random.Random(20260725))
    statement = dialect.insert_ignore("listening_history", TRACK_COLUMNS,
                                      conflict="played_at")
    for row in rows:
        cursor.execute(statement, row)
    conn.commit()

    total = cursor.execute("SELECT COUNT(*) FROM listening_history").fetchone()[0]
    conn.close()
    return total


def main():
    if os.getenv("DATABASE_URL"):
        print("DATABASE_URL is set — refusing to seed a remote database.")
        print("Re-run as:  DATABASE_URL= ./venv/bin/python scripts/seed_local_db.py")
        sys.exit(1)

    days = DEFAULT_DAYS
    if "--days" in sys.argv:
        days = int(sys.argv[sys.argv.index("--days") + 1])

    total = seed(days, reset="--reset" in sys.argv)
    print(f"\nSeeded {days} days — {total} plays in the local database.")
    print("Now run:  DATABASE_URL= ./venv/bin/python server.py")


if __name__ == "__main__":
    main()
