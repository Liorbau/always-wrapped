"""Playlist shelf HTTP API — list public, feedback owner-gated.

Runnable directly:  ./venv/bin/python tests/test_playlists_api.py
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from tests import sandbox  # noqa: F401  — must precede every app import

os.environ.setdefault("OWNER_TOKEN", "test-owner-secret")

from agents.store import playlists
from app.errors import UNAUTHORIZED
from tests.test_store import temp_db

import server


def unlocked_client():
    client = server.app.test_client()
    unlocked = client.post("/api/owner/unlock", json={"token": os.environ["OWNER_TOKEN"]})
    assert unlocked.status_code == 200, unlocked.get_json()
    return client


def test_list_playlists_is_public_and_includes_feedback():
    with temp_db():
        playlists.upsert_pushed(
            "p1",
            {"name": "Run Fuel", "tracks": [{"track_id": "t1"}],
             "description": "tempo"},
            url="https://open.spotify.com/playlist/abc",
            pushed_at="2026-08-01T10:00:00",
        )
        playlists.upsert_feedback("p1", "vibe_fit", 4, note="good")

        client = server.app.test_client()
        r = client.get("/api/agent/playlists")
        assert r.status_code == 200
        body = r.get_json()
        assert body["type"] == "playlists"
        assert len(body["playlists"]) == 1
        row = body["playlists"][0]
        assert row["id"] == "p1" and row["name"] == "Run Fuel"
        assert row["feedback"][0]["criterion"] == "vibe_fit"
        assert row["feedback"][0]["score"] == 4.0
        assert "outcome" in row
        assert body["learning_outcomes"]["disclaimer"]


def test_feedback_requires_owner_and_validates():
    with temp_db():
        playlists.upsert_pushed(
            "p1",
            {"name": "Mix", "tracks": []},
            url="u",
            pushed_at="2026-08-01T10:00:00",
        )
        locked = server.app.test_client()
        denied = locked.post(
            "/api/agent/playlists/p1/feedback",
            json={"criterion": "vibe_fit", "score": 5},
        )
        assert denied.status_code == 401
        assert denied.get_json()["error"]["code"] == UNAUTHORIZED

        client = unlocked_client()
        bad_id = client.post(
            "/api/agent/playlists/nope/feedback",
            json={"criterion": "vibe_fit", "score": 5},
        )
        assert bad_id.status_code == 404

        bad_crit = client.post(
            "/api/agent/playlists/p1/feedback",
            json={"criterion": "loudness", "score": 5},
        )
        assert bad_crit.status_code == 400

        bad_score = client.post(
            "/api/agent/playlists/p1/feedback",
            json={"criterion": "vibe_fit", "score": 9},
        )
        assert bad_score.status_code == 400

        ok = client.post(
            "/api/agent/playlists/p1/feedback",
            json={"scores": {"vibe_fit": 5, "flow": 3}, "note": "solid"},
        )
        assert ok.status_code == 200
        body = ok.get_json()
        assert body["type"] == "playlist_feedback"
        assert set(body["saved"]) == {"vibe_fit", "flow"}
        by_crit = {f["criterion"]: f for f in body["feedback"]}
        assert by_crit["vibe_fit"]["score"] == 5.0
        assert by_crit["flow"]["score"] == 3.0


def test_owner_auth_lists_feedback_post():
    """POST feedback is a mutation — must appear in the owner-auth suite’s spirit."""
    client = server.app.test_client()
    r = client.post("/api/agent/playlists/x/feedback", json={})
    assert r.status_code == 401


if __name__ == "__main__":
    test_list_playlists_is_public_and_includes_feedback()
    test_feedback_requires_owner_and_validates()
    test_owner_auth_lists_feedback_post()
    print("OK: all playlists API tests passed")
