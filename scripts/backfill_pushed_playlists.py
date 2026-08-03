"""Import approved DJ playlists into pushed_playlists (idempotent).

Sources (both optional):
  1. hitl_decision rows with decision='pushed' (primary — survives deploys)
  2. legacy agent-runs/pushes.jsonl if still on disk

Safe to re-run: each row keys on a stable id (HITL id, or sha1 of the jsonl line).

    ./venv/bin/python scripts/backfill_pushed_playlists.py [--dry-run] [DIR]
"""

import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from agents.store import hitl, playlists
from core.logging import configure_logger
from core.paths import RUNTIME_DIR
from db.connection import get_db_connection
from db.dialects import dialect_for

logger = configure_logger(__name__)

LEGACY_DIR = os.path.join(RUNTIME_DIR, "agent-runs")


def _preview_hitl():
    conn, driver = get_db_connection()
    if conn is None:
        print("  hitl_decision: no DB connection")
        return 0
    try:
        hitl._ensure_table(conn)
        p = dialect_for(driver).placeholder
        cursor = conn.cursor()
        cursor.execute(
            "SELECT id, ts, playlist FROM hitl_decision "
            f"WHERE decision = {p} ORDER BY ts ASC",
            (hitl.PUSHED,),
        )
        rows = cursor.fetchall()
    finally:
        conn.close()
    for record_id, ts, playlist_json in rows:
        try:
            name = (json.loads(playlist_json) or {}).get("name")
        except (TypeError, ValueError):
            name = "?"
        print(f"  would import hitl {record_id}: {name!r} ({ts})")
    print(f"  hitl_decision: {len(rows)} pushed row(s)")
    return len(rows)


def _preview_jsonl(directory):
    path = os.path.join(directory, "pushes.jsonl")
    if not os.path.isfile(path):
        print(f"  pushes.jsonl: not found at {path}, skipping")
        return 0
    n = 0
    with open(path) as handle:
        for line in handle:
            if not line.strip():
                continue
            try:
                entry = json.loads(line)
            except ValueError:
                continue
            name = (entry.get("playlist") or {}).get("name")
            print(f"  would import jsonl: {name!r} ({entry.get('ts')})")
            n += 1
    print(f"  pushes.jsonl: {n} row(s)")
    return n


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    directory = args[0] if args else LEGACY_DIR
    dry_run = "--dry-run" in sys.argv

    print(f"{'Previewing' if dry_run else 'Importing'} pushed playlists…")
    if dry_run:
        total = _preview_hitl() + _preview_jsonl(directory)
        print(f"\nDry run — nothing written ({total} would upsert).")
        return

    if not playlists.ensure_tables():
        print("Could not create tables — aborting.")
        return
    n_hitl = playlists.import_from_hitl()
    n_jsonl = playlists.import_from_jsonl(directory)
    print(f"  hitl_decision: {n_hitl} upserted")
    print(f"  pushes.jsonl: {n_jsonl} upserted")
    print(f"\nUpserted {n_hitl + n_jsonl} playlist(s).")


if __name__ == "__main__":
    main()
