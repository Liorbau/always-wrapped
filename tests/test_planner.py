"""Planner + Telegram tests — offline (FakeLLM, stubbed DJ + requests).

Runnable directly:  ./venv/bin/python tests/test_planner.py
"""

import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from tests import sandbox  # noqa: F401  — must precede every app import

import agents.planner as planner
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


if __name__ == "__main__":
    test_plan_tomorrow_builds_per_wanted_block()
    test_plan_no_blocks_no_llm_cost()
    print("OK: all planner tests passed")
