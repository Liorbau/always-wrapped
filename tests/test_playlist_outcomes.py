"""Deterministic DJ playlist outcomes — skips, ratings, cohorts.

Runnable directly:  ./venv/bin/python tests/test_playlist_outcomes.py
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from tests import sandbox  # noqa: F401  — must precede every app import

from agents import playlist_outcomes as po
from agents.playlist_outcomes import queries as outcome_queries
from agents.store import hitl, playlists
from tests.test_store import temp_db


def test_classify_gaps_skip_complete_unknown():
    plays = [
        {"played_at": "2026-08-01T10:00:00", "track_id": "a", "duration_ms": 200_000},
        {"played_at": "2026-08-01T10:01:00", "track_id": "b", "duration_ms": 200_000},  # 60s gap → skip
        {"played_at": "2026-08-01T10:05:00", "track_id": "c", "duration_ms": 200_000},  # 4min → complete
    ]
    rows = po.classify_gaps(plays)
    assert rows[0]["outcome"] == "skipped"
    assert rows[1]["outcome"] == "completed"
    assert rows[2]["outcome"] == "unknown"  # no next play


def test_never_played_and_no_fake_rates():
    pl = {
        "id": "p1", "name": "Empty", "pushed_at": "2026-08-01T09:00:00",
        "tracks": [{"track_id": "t1"}],
    }
    out = po.outcome_for_playlist(pl, history_plays=[])
    assert out["status"] == "never_played"
    assert out["skip_rate"] is None and out["completion_rate"] is None
    assert "Never played" in out["note"]


def test_outcome_counts_plays_after_push_only():
    pl = {
        "id": "p1", "name": "Mix", "pushed_at": "2026-08-01T12:00:00",
        "tracks": [
            {"track_id": "t1"}, {"track_id": "t2"}, {"track_id": "t3"},
        ],
        "context": {
            "decision_trace": {
                "facts": {"exploration": {"track_ids": ["t3"]}},
            },
        },
    }
    history = [
        # before push — ignored
        {"played_at": "2026-08-01T11:00:00", "track_id": "t1", "duration_ms": 180_000},
        {"played_at": "2026-08-01T12:10:00", "track_id": "t1", "duration_ms": 180_000},
        {"played_at": "2026-08-01T12:14:00", "track_id": "t2", "duration_ms": 180_000},  # complete
        {"played_at": "2026-08-01T12:15:00", "track_id": "t3", "duration_ms": 180_000},  # skip vs next
        {"played_at": "2026-08-01T12:16:00", "track_id": "t2", "duration_ms": 180_000},  # unknown last
    ]
    out = po.outcome_for_playlist(pl, history, feedback=[
        {"criterion": "overall", "score": 4},
        {"criterion": "vibe_fit", "score": 5},
    ])
    assert out["status"] == "observed"
    assert out["n_played_unique"] == 3
    assert out["time_to_first_play_sec"] == 600.0
    assert out["mean_rating"] == 4.5
    assert out["exploration"]["n_flagged"] == 1
    assert out["attribution"] == "track_played_after_push"


def test_cohorts_split_on_bias_cutoff():
    outcomes = [
        {"pushed_at": "2026-07-01T00:00:00", "status": "observed",
         "n_skipped": 2, "n_completed": 2, "mean_rating": 3,
         "time_to_first_play_sec": 10},
        {"pushed_at": "2026-08-01T00:00:00", "status": "observed",
         "n_skipped": 0, "n_completed": 4, "mean_rating": 5,
         "time_to_first_play_sec": 20},
    ]
    roll = po.cohort_rollups(outcomes, "2026-07-15T00:00:00")
    assert roll["before"]["n"] == 1 and roll["after"]["n"] == 1
    assert roll["before"]["skip_rate"] == 0.5
    assert roll["after"]["skip_rate"] == 0.0
    assert "not causal" in roll["note"].lower() or "Descriptive" in roll["note"]


def test_learning_summary_roundtrip_with_db():
    with temp_db():
        original = outcome_queries.get_db_connection
        outcome_queries.get_db_connection = playlists.get_db_connection
        try:
            playlists.upsert_pushed(
                "pl-a",
                {"name": "A", "tracks": [{"track_id": "t1", "duration_ms": 200000}]},
                url="u",
                pushed_at="2026-08-01T10:00:00",
            )
            hitl.record_push({"name": "A"}, "u", ts="2026-08-01T10:00:00", record_id="pl-a")
            hitl.record_rejection({"name": "Nope"}, "meh", ts="2026-08-01T11:00:00")

            conn, _ = playlists.get_db_connection()
            try:
                conn.execute(
                    """CREATE TABLE IF NOT EXISTS listening_history (
                        played_at TEXT PRIMARY KEY, track_id TEXT, track_name TEXT,
                        artist_name TEXT, duration_ms INTEGER)"""
                )
                conn.execute(
                    "INSERT INTO listening_history VALUES (?,?,?,?,?)",
                    ("2026-08-01T10:30:00", "t1", "Song", "Art", 200000),
                )
                conn.execute(
                    "INSERT INTO listening_history VALUES (?,?,?,?,?)",
                    ("2026-08-01T10:31:00", "t1", "Song", "Art", 200000),
                )
                conn.execute(
                    """CREATE TABLE IF NOT EXISTS preference_bias (
                        kind TEXT, key TEXT, weight REAL, sample_n INTEGER,
                        updated_at TEXT, evidence TEXT, PRIMARY KEY (kind, key))"""
                )
                conn.execute(
                    "INSERT INTO preference_bias VALUES (?,?,?,?,?,?)",
                    ("artist", "Art", 0.2, 3, "2026-07-20T00:00:00", "e"),
                )
                conn.commit()
            finally:
                conn.close()

            summary = po.learning_summary(limit=10)
            assert summary["hitl"]["pushed"] == 1
            assert summary["hitl"]["rejected"] == 1
            assert summary["hitl"]["approve_rate"] == 0.5
            assert summary["n_playlists"] == 1
            assert summary["per_playlist"][0]["n_plays"] == 2
            assert summary["bias_cutoff"] == "2026-07-20T00:00:00"
            line = po.observatory_line(summary)
            assert line["n_playlists"] == 1
            assert "Descriptive" in line["disclaimer"]
        finally:
            outcome_queries.get_db_connection = original


if __name__ == "__main__":
    test_classify_gaps_skip_complete_unknown()
    test_never_played_and_no_fake_rates()
    test_outcome_counts_plays_after_push_only()
    test_cohorts_split_on_bias_cutoff()
    test_learning_summary_roundtrip_with_db()
    print("OK: all playlist_outcomes tests passed")
