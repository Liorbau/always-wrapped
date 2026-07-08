"""Planner + Telegram tests — offline (FakeLLM, stubbed DJ + requests).

Runnable directly:  ./venv/bin/python tests/test_planner.py
"""

import json
import os
import sys
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import agents.planner as planner
import agents.telegram as tg
from tests.test_harness import FakeLLM
from tests.test_calendar import ICS, NOW


def test_plan_tomorrow_builds_per_wanted_block():
    # LLM brief: music for the run, skip the project block
    brief = {"satisfied": True, "plans": [
        {"title": "Morning run", "skip": False, "brief": "a 30-min high-energy run playlist"},
        {"title": "Deep work: project", "skip": True},
    ]}
    llm = FakeLLM([{"content": json.dumps(brief)}])
    calls = []

    def fake_dj(dj, message):
        calls.append(message)
        return {"playlist": {"name": "Run Fuel", "tracks": [{"track_id": "t1"}]},
                "response": "built", "cost_usd": 0.05}

    orig = planner.build_dj
    planner.build_dj = lambda llm=None: object()
    try:
        out = planner.plan_tomorrow(ics_text=ICS, now=NOW, llm=llm, dj_run=fake_dj)
    finally:
        planner.build_dj = orig

    assert out["date"] == "2026-07-09"
    assert len(out["proposals"]) == 1                     # run built, project skipped
    p = out["proposals"][0]
    assert p["block"]["title"] == "Morning run"
    assert p["playlist"]["name"] == "Run Fuel"
    assert calls == ["a 30-min high-energy run playlist"]  # brief reached the DJ
    assert out["cost_usd"] > 0


def test_plan_no_blocks_no_llm_cost():
    empty = "BEGIN:VCALENDAR\nVERSION:2.0\nPRODID:-//t//EN\nEND:VCALENDAR"
    out = planner.plan_tomorrow(ics_text=empty, now=NOW, llm=FakeLLM([{"content": "{}"}]))
    assert out["proposals"] == [] and out["cost_usd"] == 0.0


def test_telegram_send_proposal_shape():
    sent = {}

    class FakeResp:
        def json(self): return {"ok": True, "result": {"message_id": 5}}

    orig = tg.requests.post
    tg.requests.post = lambda url, json, timeout: (sent.update(url=url, payload=json), FakeResp())[1]
    os.environ["TELEGRAM_BOT_TOKEN"] = "T"
    os.environ["TELEGRAM_CHAT_ID"] = "42"
    try:
        r = tg.send_proposal({"title": "Morning run", "start": "07:00"},
                             {"name": "Run Fuel", "tracks": [{"track_name": "Go"}]}, "pid123")
        assert r["ok"] is True
        assert "sendMessage" in sent["url"]
        kb = sent["payload"]["reply_markup"]["inline_keyboard"][0]
        assert kb[0]["callback_data"] == "approve:pid123"
        assert kb[1]["callback_data"] == "reject:pid123"
    finally:
        tg.requests.post = orig
        del os.environ["TELEGRAM_BOT_TOKEN"], os.environ["TELEGRAM_CHAT_ID"]


def test_telegram_missing_token():
    os.environ.pop("TELEGRAM_BOT_TOKEN", None)
    r = tg.send_proposal({"title": "x", "start": "07:00"}, {"tracks": []}, "p")
    assert "error" in r


if __name__ == "__main__":
    test_plan_tomorrow_builds_per_wanted_block()
    test_plan_no_blocks_no_llm_cost()
    test_telegram_send_proposal_shape()
    test_telegram_missing_token()
    print("OK: all planner tests passed")
