"""Owner unlock: cookie gate for browser mutations.

Runnable directly:  ./venv/bin/python tests/test_owner_auth.py
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from tests import sandbox  # noqa: F401  — must precede every app import

os.environ["OWNER_TOKEN"] = "test-owner-secret"

from app import create_app
from app import owner_auth
from app.errors import UNAUTHORIZED


def _client():
    app = create_app()
    app.config["TESTING"] = True
    return app.test_client()


def test_mutations_fail_closed_without_cookie():
    client = _client()
    for path in (
        "/api/agent/chat",
        "/api/agent/approve",
        "/api/agent/reject",
        "/api/agent/evaluate",
        "/api/agent/plan",
        "/api/agent/run/x/stop",
        "/api/agent/playlists/x/feedback",
        "/api/refresh",
    ):
        response = client.post(path, json={})
        assert response.status_code == 401, path
        assert response.get_json()["error"]["code"] == UNAUTHORIZED


def test_reads_stay_public():
    client = _client()
    status = client.get("/api/owner/status")
    assert status.status_code == 200
    assert status.get_json()["unlocked"] is False
    # activity / playlist shelf are public reads — must not demand the owner cookie
    assert client.get("/api/agent/activity").status_code != 401
    assert client.get("/api/agent/playlists").status_code != 401


def test_wrong_password_rejected():
    client = _client()
    response = client.post("/api/owner/unlock", json={"token": "nope"})
    assert response.status_code == 401
    assert "aw_owner" not in response.headers.getlist("Set-Cookie")


def test_unlock_sets_cookie_and_opens_mutations():
    client = _client()
    unlock = client.post("/api/owner/unlock", json={"token": "test-owner-secret"})
    assert unlock.status_code == 200
    assert unlock.get_json()["unlocked"] is True
    assert client.get("/api/owner/status").get_json()["unlocked"] is True

    # chat still validates the message, but auth is past — not 401
    chat = client.post("/api/agent/chat", json={"message": ""})
    assert chat.status_code != 401


def test_missing_owner_token_fails_closed(monkeypatch=None):
    # without OWNER_TOKEN, unlock and mutations stay locked
    previous = os.environ.pop("OWNER_TOKEN", None)
    try:
        client = _client()
        assert client.post("/api/owner/unlock", json={"token": "x"}).status_code == 401
        assert client.post("/api/agent/approve", json={}).status_code == 401
        assert client.get("/api/owner/status").get_json()["unlocked"] is False
    finally:
        if previous is not None:
            os.environ["OWNER_TOKEN"] = previous


def test_cookie_round_trip_helpers():
    value = owner_auth.issue_cookie_value()
    assert owner_auth.cookie_is_valid(value)
    assert not owner_auth.cookie_is_valid("tampered")
    assert not owner_auth.cookie_is_valid("")


def test_cross_origin_mutation_rejected():
    client = _client()
    client.post("/api/owner/unlock", json={"token": "test-owner-secret"})
    response = client.post(
        "/api/agent/approve",
        json={},
        headers={"Origin": "https://evil.example"},
    )
    assert response.status_code == 401


if __name__ == "__main__":
    test_mutations_fail_closed_without_cookie()
    test_reads_stay_public()
    test_wrong_password_rejected()
    test_unlock_sets_cookie_and_opens_mutations()
    test_missing_owner_token_fails_closed()
    test_cookie_round_trip_helpers()
    test_cross_origin_mutation_rejected()
    print("OK: all owner auth tests passed")
