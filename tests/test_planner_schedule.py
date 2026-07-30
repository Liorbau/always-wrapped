"""Chat /plantime command and planner-time HTTP endpoints.

Runnable directly:  ./venv/bin/python tests/test_planner_schedule.py
"""

import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from tests import sandbox  # noqa: F401

os.environ.setdefault("OWNER_TOKEN", "test-owner-secret")

import sqlite3

from agents import timers
from app.modules.agent_api.orchestrators import planner_schedule, send_chat
from db import settings as db_settings
import server


def _patch_settings(path):
    def connect(readonly=False):
        return sqlite3.connect(path), "sqlite"
    timers.get_db_connection = connect
    db_settings.get_db_connection = connect


def _unlocked():
    client = server.app.test_client()
    assert client.post("/api/owner/unlock",
                       json={"token": os.environ["OWNER_TOKEN"]}).status_code == 200
    return client


def test_chat_plantime_command_roundtrip():
    with tempfile.NamedTemporaryFile(suffix=".db") as tmp:
        _patch_settings(tmp.name)
        out = send_chat.execute("/plantime")
        assert out["type"] == "plantime" and out["enabled"] is False
        out = send_chat.execute("/plantime 21:00")
        assert out["at"] == "21:00" and "21:00" in out["response"]
        out = send_chat.execute("/plantime off")
        assert out["enabled"] is False


def test_http_planner_time_requires_owner_and_updates():
    with tempfile.NamedTemporaryFile(suffix=".db") as tmp:
        _patch_settings(tmp.name)
        locked = server.app.test_client()
        assert locked.get("/api/agent/planner-time").status_code == 401

        client = _unlocked()
        assert client.get("/api/agent/planner-time").get_json()["enabled"] is False
        put = client.put("/api/agent/planner-time", json={"at": "07:30"})
        assert put.status_code == 200 and put.get_json()["at"] == "07:30"
        off = client.put("/api/agent/planner-time", json={"at": None})
        assert off.get_json()["enabled"] is False


def test_apply_rejects_bad_time():
    try:
        planner_schedule.apply("25:99")
    except Exception as exc:
        assert exc.status == 400
    else:
        raise AssertionError("accepted bad time")


if __name__ == "__main__":
    test_chat_plantime_command_roundtrip()
    test_http_planner_time_requires_owner_and_updates()
    test_apply_rejects_bad_time()
    print("OK: all planner schedule tests passed")
