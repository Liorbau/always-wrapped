"""Agent tools: guarded read-only SQL over listening_history.

The DJ writes its own SELECT statements (max agentic depth); this module is
the safety fence around them. Defense in depth, three layers:

  1. statement guard  — SELECT/WITH only, single statement, no write keywords
  2. connection guard — the DB connection itself is opened read-only
  3. row cap          — results truncated at MAX_ROWS regardless of the SQL

Query results contain track/artist names — untrusted input. They are returned
as data for the model to read, and the DJ's system prompt must fence them as
content, never instructions (see AGENTS.md).
"""

import json
import os
import re

from db.connection import get_db_connection
from core.logging import configure_logger

logger = configure_logger(__name__)

MAX_ROWS = 100
SQL_DIALECT = "PostgreSQL" if os.getenv("DATABASE_URL") else "SQLite"

# ponytail: word-boundary keyword blocklist — a SELECT containing the *string*
# 'delete' in a quoted literal would be wrongly rejected; acceptable ceiling,
# revisit only if the agent actually hits it.
FORBIDDEN = re.compile(
    r"\b(insert|update|delete|drop|alter|create|truncate|grant|revoke|"
    r"attach|detach|pragma|vacuum|copy|reindex|replace)\b",
    re.IGNORECASE,
)

SCHEMA_DOC = f"""SQL dialect: {SQL_DIALECT}.
Table listening_history (one row = one play):
  played_at TEXT primary key — ISO-8601 UTC, e.g. '2026-07-07T08:33:26.231Z' (sortable as text)
  track_id TEXT, track_name TEXT, artist_name TEXT, album_name TEXT
  artist_id TEXT, album_image_url TEXT, artist_image_url TEXT
  duration_ms INTEGER — track length; NULL only on legacy rows
  artist_genres TEXT — comma-separated, e.g. 'pop, dance pop'; '' = artist has
    no genres on Spotify; NULL = never fetched. Filter with LIKE '%genre%'.
  album_release_date TEXT — '1977-02-04' or just '1977'. Decades/eras filter
    by string prefix: 60s = >= '1960' AND < '1970'.
Notes: ~4.3k rows since 2026-02-10. Timestamps are UTC. A track was likely
skipped when the gap to the next played_at is much smaller than duration_ms.
Language/locale: detect Hebrew tracks with track_name ~ '[א-ת]' (PostgreSQL) —
the history holds hundreds of them. Genre labels are unreliable for locale:
Israeli artists appear as 'mizrahi', '' or NULL — never filter history by
'israeli' genre labels.
Results consume your context — SELECT only needed columns, aggregate in SQL,
and use LIMIT instead of fetching everything."""


def validate_sql(sql):
    """Return an error string if the SQL is not a safe single SELECT, else None."""
    stripped = sql.strip().rstrip(";").strip()
    if not stripped:
        return "Empty SQL."
    if ";" in stripped:
        return "Multiple statements are not allowed."
    if not re.match(r"^(select|with)\b", stripped, re.IGNORECASE):
        return "Only SELECT (or WITH ... SELECT) queries are allowed."
    match = FORBIDDEN.search(stripped)
    if match:
        return f"Forbidden keyword: {match.group(0)!r}. This tool is read-only."
    return None


def query_history(args):
    """Tool entrypoint: run guarded read-only SQL, return JSON result string."""
    sql = args.get("sql", "")
    error = validate_sql(sql)
    if error:
        logger.warning("query_history rejected SQL: %s | %s", error, sql[:120])
        return json.dumps({"error": error})

    conn, driver = get_db_connection(readonly=True)
    if not conn:
        return json.dumps({"error": "Database connection failed."})
    try:
        cursor = conn.cursor()
        cursor.execute(sql.strip().rstrip(";"))
        columns = [c[0] for c in cursor.description]
        rows = cursor.fetchmany(MAX_ROWS)
        truncated = cursor.fetchone() is not None
        result = {
            "columns": columns,
            "rows": [list(r) for r in rows],
            "row_count": len(rows),
            "truncated": truncated,
        }
        logger.info("query_history: %d rows%s | %s",
                    len(rows), " (truncated)" if truncated else "", sql[:120])
        return json.dumps(result, default=str)
    except Exception as exc:
        # SQL errors go back to the model so it can correct and retry
        return json.dumps({"error": f"{type(exc).__name__}: {exc}"})
    finally:
        conn.close()


QUERY_HISTORY_SCHEMA = {
    "type": "function",
    "function": {
        "name": "query_history",
        "description": (
            "Run a read-only SQL SELECT against the user's Spotify listening "
            "history. Use it to explore taste, familiarity, time-of-day "
            "patterns, and pick candidate tracks.\n" + SCHEMA_DOC
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "sql": {
                    "type": "string",
                    "description": "A single SELECT (or WITH) statement. "
                    f"Results are capped at {MAX_ROWS} rows.",
                }
            },
            "required": ["sql"],
        },
    },
}

