"""Durable pending proposals: restart-safe, single-use, 24h expiry.

Runnable directly:  ./venv/bin/python tests/test_proposals.py
"""

import os
import sys
import tempfile
from datetime import datetime, timedelta, timezone

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from tests import sandbox  # noqa: F401

import sqlite3

from agents.store import pending_proposals as store
from app.errors import AppError
from app.modules.agent_api import proposals


def _patch(path):
    def connect(readonly=False):
        return sqlite3.connect(path), "sqlite"
    store.get_db_connection = connect


def test_register_survives_reconnect():
    with tempfile.NamedTemporaryFile(suffix=".db") as tmp:
        _patch(tmp.name)
        pid = proposals.register({"name": "Mix", "tracks": []})
        assert proposals.is_pending(pid)
        # new connection — still there
        assert store.is_pending(pid)


def test_approve_is_single_use_and_restores_on_spotify_failure():
    with tempfile.NamedTemporaryFile(suffix=".db") as tmp:
        _patch(tmp.name)
        pid = proposals.register({"name": "Mix", "tracks": [{"track_id": "t1"}]})
        pushed = []

        def boom(pl):
            return {"error": "spotify down"}

        def ok(pl):
            pushed.append(pl)
            return {"playlist_id": "x", "url": "https://s", "track_count": 1}

        original = proposals.push_playlist
        try:
            proposals.push_playlist = boom
            try:
                proposals.push(pid)
            except AppError as exc:
                assert exc.code == "UPSTREAM_ERROR"
            else:
                raise AssertionError("expected upstream error")
            assert proposals.is_pending(pid)  # restored for retry

            proposals.push_playlist = ok
            out = proposals.push(pid)
            assert out["url"] == "https://s" and len(pushed) == 1
            assert not proposals.is_pending(pid)

            try:
                proposals.push(pid)
            except AppError as exc:
                assert exc.code == "NOT_FOUND"
            else:
                raise AssertionError("replay should fail")
        finally:
            proposals.push_playlist = original


def test_reject_and_discard():
    with tempfile.NamedTemporaryFile(suffix=".db") as tmp:
        _patch(tmp.name)
        pid = proposals.register({"name": "A", "tracks": []})
        proposals.reject(pid, "meh")
        assert not proposals.is_pending(pid)
        assert proposals.discard("missing") is None


def test_expiry_blocks_claim():
    with tempfile.NamedTemporaryFile(suffix=".db") as tmp:
        _patch(tmp.name)
        pid = proposals.register({"name": "Old", "tracks": []})
        conn = sqlite3.connect(tmp.name)
        past = (datetime.now(timezone.utc) - timedelta(hours=1)).strftime(
            "%Y-%m-%dT%H:%M:%SZ")
        conn.execute(
            "UPDATE pending_proposal SET expires_at = ? WHERE id = ?", (past, pid))
        conn.commit()
        conn.close()
        try:
            proposals.take(pid)
        except AppError as exc:
            assert exc.code == "NOT_FOUND"
        else:
            raise AssertionError("expired proposal was claimable")
        conn = sqlite3.connect(tmp.name)
        status = conn.execute(
            "SELECT status FROM pending_proposal WHERE id = ?", (pid,)).fetchone()[0]
        conn.close()
        assert status == store.EXPIRED


if __name__ == "__main__":
    test_register_survives_reconnect()
    test_approve_is_single_use_and_restores_on_spotify_failure()
    test_reject_and_discard()
    test_expiry_blocks_claim()
    print("OK: all proposal tests passed")
