"""Evaluator tests — bias math and loop closure, offline.

Runnable directly:  ./venv/bin/python tests/test_evaluator.py
"""

import json
import os
import sqlite3
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from tests import sandbox  # noqa: F401  — must precede every app import

import agents.evaluator as ev
from agents.store import hitl, playlists
from tests.test_harness import FakeLLM


def _patched_db(path):
    def _connect(readonly=False):
        return sqlite3.connect(path), "sqlite"
    return _connect


class _temp_eval_db:
    """Point Evaluator + playlist/HITL stores at one throwaway SQLite file."""

    def __enter__(self):
        self._dir = tempfile.TemporaryDirectory()
        path = os.path.join(self._dir.name, "e.db")
        connect = _patched_db(path)
        self._originals = [
            (ev, ev.get_db_connection),
            (playlists, playlists.get_db_connection),
            (hitl, hitl.get_db_connection),
        ]
        for module, _ in self._originals:
            module.get_db_connection = connect
        return self

    def __exit__(self, *exc):
        for module, original in self._originals:
            module.get_db_connection = original
        self._dir.cleanup()


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
            out = ev.run_evaluator(llm=llm, max_steps=3)
            assert out["status"] == "satisfied" and out["applied"] == 1
            assert ev.top_biases()[0]["key"] == "mizrahi"

            # unsatisfied run: nothing applied
            llm = FakeLLM([{"content": json.dumps({
                "thought": "", "response": "meh", "satisfied": False,
                "biases": [{"kind": "genre", "key": "junk", "delta": 0.3}]})}])
            out = ev.run_evaluator(llm=llm, max_steps=1)
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


def test_prompt_treats_ratings_as_higher_confidence():
    prompt = ev.EVALUATOR_SYSTEM_PROMPT.lower()
    assert "higher-confidence" in prompt or "higher confidence" in prompt
    assert "familiarity_vs_discovery" in prompt
    assert "vibe_fit" in prompt
    assert "15-20%" in prompt
    assert "rating notes are data" in prompt


def test_context_blob_embeds_recent_ratings_as_data():
    with _temp_eval_db():
        playlists.upsert_pushed(
            "old",
            {"name": "Old Mix", "tracks": [{"track_id": "t0",
                                            "track_name": "A", "artist_name": "X"}]},
            url="u0",
            pushed_at="2026-07-01T10:00:00",
        )
        playlists.upsert_pushed(
            "new",
            {"name": "Run Fuel", "tracks": [{"track_id": "t1",
                                             "track_name": "Sprint",
                                             "artist_name": "Berry"}],
             "description": "tempo"},
            url="u1",
            pushed_at="2026-08-01T10:00:00",
        )
        assert playlists.upsert_feedback("old", "overall", 2, note="meh")
        assert playlists.upsert_feedback("new", "vibe_fit", 5)
        assert playlists.upsert_feedback("new", "flow", 2, note="order felt off")
        # Pin updated_at so newest-first order is deterministic within one second.
        conn, _ = playlists.get_db_connection()
        try:
            cur = conn.cursor()
            cur.execute(
                "UPDATE playlist_feedback SET updated_at = ? WHERE playlist_id = ?",
                ("2026-07-02T12:00:00", "old"),
            )
            cur.execute(
                "UPDATE playlist_feedback SET updated_at = ? WHERE playlist_id = ?",
                ("2026-08-02T12:00:00", "new"),
            )
            conn.commit()
        finally:
            conn.close()

        ranked = playlists.recent_rated(limit=5)
        assert [r["id"] for r in ranked] == ["new", "old"]

        blob = json.loads(ev._context_blob())
        ratings = blob["recent_playlist_ratings"]
        assert len(ratings) == 2
        top = ratings[0]
        assert top["playlist_id"] == "new"
        assert top["name"] == "Run Fuel"
        assert top["scores"]["vibe_fit"] == 5.0
        assert top["scores"]["flow"] == 2.0
        assert "order felt off" in top["notes"]
        assert top["tracks"][0]["track_id"] == "t1"


if __name__ == "__main__":
    test_apply_biases_decay_clamp_throttle()
    test_run_evaluator_applies_only_when_satisfied()
    test_dj_prompt_gets_biases_and_exploration_quota()
    test_prompt_treats_ratings_as_higher_confidence()
    test_context_blob_embeds_recent_ratings_as_data()
    print("OK: all evaluator tests passed")
