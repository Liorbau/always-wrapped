"""Import the legacy approve/reject history into the database (idempotent).

The HITL decisions used to be appended to pushes.jsonl / rejections.jsonl under
the runtime directory, which a deploy erases. They now live in `hitl_decision`,
because that history is the Evaluator's entire training signal.

    ./venv/bin/python scripts/backfill_agent_runs.py [--dry-run] [DIR]

Run costs are deliberately not imported: the cap is per-day, so a July run's
cost has no bearing on today's budget. Safe to re-run — each decision keys on a
hash of its own line, so a second pass updates rather than duplicates.
"""

import hashlib
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from agents.store import hitl
from core.logging import configure_logger
from core.paths import RUNTIME_DIR

logger = configure_logger(__name__)

LEGACY_DIR = os.path.join(RUNTIME_DIR, "agent-runs")
SOURCES = (("pushes.jsonl", hitl.PUSHED), ("rejections.jsonl", hitl.REJECTED))


def import_decisions(directory, dry_run):
    imported = 0
    for filename, decision in SOURCES:
        path = os.path.join(directory, filename)
        if not os.path.exists(path):
            print(f"  {filename}: not found, skipping")
            continue
        imported += _import_file(path, decision, dry_run)
    return imported


def _import_file(path, decision, dry_run):
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

            name = (entry.get("playlist") or {}).get("name")
            if dry_run:
                print(f"  would import {decision}: {name!r} ({entry.get('ts')})")
                continue
            if _record(entry, decision, hashlib.sha1(line.strip().encode()).hexdigest()):
                imported += 1
    return imported


def _record(entry, decision, record_id):
    playlist = entry.get("playlist") or {}
    if decision == hitl.PUSHED:
        return hitl.record_push(playlist, entry.get("url"),
                                ts=entry.get("ts"), record_id=record_id)
    return hitl.record_rejection(playlist, entry.get("reason"),
                                 ts=entry.get("ts"), record_id=record_id)


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    directory = args[0] if args else LEGACY_DIR
    dry_run = "--dry-run" in sys.argv

    if not os.path.isdir(directory):
        print(f"No such directory: {directory}")
        return

    print(f"{'Previewing' if dry_run else 'Importing'} decisions from {directory}…")
    imported = import_decisions(directory, dry_run)
    print("\nDry run — nothing written." if dry_run
          else f"\nImported {imported} decision(s).")


if __name__ == "__main__":
    main()
