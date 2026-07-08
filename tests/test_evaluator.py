"""Evaluator tests — bias math and loop closure, offline.

Runnable directly:  ./venv/bin/python tests/test_evaluator.py
"""

import json
import os
import sqlite3
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import agents.evaluator as ev
from tests.test_harness import FakeLLM


def _patched_db(path):
    def _connect(readonly=False):
        return sqlite3.connect(path), "sqlite"
    return _connect


def test_apply_biases_decay_clamp_throttle():
    with tempfile.TemporaryDirectory() as tmp:
        path = os.path.join(tmp, "b.db")
        original = ev.get_db_connection
        ev.get_db_connection = _patched_db(path)
        try:
            # oversized delta gets clamped to MAX_DELTA
            applied = ev.apply_biases([{"kind": "artist", "key": "X", "delta": 0.9,
                                        "evidence": "e"}])
            assert len(applied) == 1 and applied[0]["delta"] == 0.3  # clamped
            # young weight (sample_n=1) is throttled at read time: 0.3 * 1/3 = 0.1
            [b] = ev.top_biases()
            assert b["weight"] == 0.1

            # two more runs: decay applies to the old weight, sample_n grows
            ev.apply_biases([{"kind": "artist", "key": "X", "delta": 0.3}])
            ev.apply_biases([{"kind": "artist", "key": "X", "delta": 0.3}])
            [b] = ev.top_biases()
            # weight: ((0.3*0.9)+0.3)*0.9+0.3 = 0.813; full strength at n=3
            assert abs(b["weight"] - 0.81) < 0.01

            # junk proposals are ignored
            assert ev.apply_biases([{"kind": "", "key": "y", "delta": 0.2},
                                    {"kind": "genre", "key": "z", "delta": "NaNope"},
                                    {"kind": "genre", "key": "w", "delta": 0}]) == []
        finally:
            ev.get_db_connection = original


def test_run_evaluator_applies_only_when_satisfied():
    with tempfile.TemporaryDirectory() as tmp:
        path = os.path.join(tmp, "b.db")
        original = ev.get_db_connection
        ev.get_db_connection = _patched_db(path)
        try:
            llm = FakeLLM([{"content": json.dumps({
                "thought": "t", "response": "report", "satisfied": True,
                "biases": [{"kind": "genre", "key": "mizrahi", "delta": 0.2,
                            "evidence": "completed most evening plays"}]})}])
            out = ev.run_evaluator(llm=llm, run_dir=tmp, max_steps=3)
            assert out["status"] == "satisfied" and out["applied"] == 1
            assert ev.top_biases()[0]["key"] == "mizrahi"

            # unsatisfied run: nothing applied
            llm = FakeLLM([{"content": json.dumps({
                "thought": "", "response": "meh", "satisfied": False,
                "biases": [{"kind": "genre", "key": "junk", "delta": 0.3}]})}])
            out = ev.run_evaluator(llm=llm, run_dir=tmp, max_steps=1)
            assert out["applied"] == 0
            assert all(b["key"] != "junk" for b in ev.top_biases())
        finally:
            ev.get_db_connection = original


def test_dj_prompt_gets_biases_and_exploration_quota():
    with tempfile.TemporaryDirectory() as tmp:
        path = os.path.join(tmp, "b.db")
        original = ev.get_db_connection
        ev.get_db_connection = _patched_db(path)
        try:
            for _ in range(3):  # reach full strength
                ev.apply_biases([{"kind": "artist", "key": "Berry Sakharof",
                                  "delta": 0.3}])
            block = ev.format_biases_for_dj()
            assert "Berry Sakharof" in block
            assert "exploration" in block  # the anti-echo-chamber quota
            assert "never hard rules" in block
        finally:
            ev.get_db_connection = original


if __name__ == "__main__":
    test_apply_biases_decay_clamp_throttle()
    test_run_evaluator_applies_only_when_satisfied()
    test_dj_prompt_gets_biases_and_exploration_quota()
    print("OK: all evaluator tests passed")
