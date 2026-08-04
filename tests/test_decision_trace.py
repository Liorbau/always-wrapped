"""Decision trace — facts from bias snapshot + packed playlist.

Runnable directly:  ./venv/bin/python tests/test_decision_trace.py
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from tests import sandbox  # noqa: F401  — must precede every app import

from agents.dj.decision_trace import attach_decision_trace, build_decision_trace
from agents.store import playlists


def _playlist():
    return {
        "name": "Run Fuel",
        "description": "tempo",
        "familiarity_constraint": "mixed",
        "target_duration_min": 30,
        "total_duration_min": 28.5,
        "tracks": [
            {"track_id": "t1", "track_name": "A", "artist_name": "Berry Sakharof",
             "familiarity": "familiar", "reason": "model said so"},
            {"track_id": "t2", "track_name": "B", "artist_name": "Someone New",
             "familiarity": "never", "reason": "explore?"},
            {"track_id": "t3", "track_name": "C", "artist_name": "Berry Sakharof",
             "familiarity": "heavy", "reason": "again"},
            {"track_id": "t4", "track_name": "D", "artist_name": "Other Act",
             "familiarity": "never", "reason": "fresh"},
            {"track_id": "t5", "track_name": "E", "artist_name": "Other Act",
             "familiarity": "rare", "reason": "fill"},
        ],
    }


def test_trace_matches_biases_and_marks_exploration_heuristic():
    biases = [{
        "kind": "artist", "key": "Berry Sakharof", "weight": 0.3,
        "sample_n": 5, "evidence": "completed evenings", "weak": False,
    }]
    trace = build_decision_trace(_playlist(), biases, violations=[])
    assert trace["version"] == 1
    [row] = trace["facts"]["biases"]
    assert row["matched_n"] == 2
    assert set(row["matched_track_ids"]) == {"t1", "t3"}
    assert row["weak"] is False
    # 3 of 5 tracks outside the positive artist pref
    assert trace["facts"]["exploration"]["approx_pct"] == 60
    assert set(trace["facts"]["exploration"]["track_ids"]) == {"t2", "t4", "t5"}
    assert "heuristic" in trace["facts"]["exploration"]["note"].lower()
    assert any("Berry Sakharof" in line for line in trace["summary"])
    assert "model-written" in trace["model_vs_facts"]


def test_trace_honest_when_no_artist_prefs():
    trace = build_decision_trace(_playlist(), [], violations=["dup"])
    assert trace["facts"]["exploration"]["approx_pct"] is None
    assert any("No learned preferences" in line for line in trace["summary"])
    assert any("Verifier repaired" in line for line in trace["summary"])


def test_weak_evidence_called_out():
    biases = [{
        "kind": "artist", "key": "Berry Sakharof", "weight": 0.1,
        "sample_n": 1, "evidence": "", "weak": True,
    }]
    trace = build_decision_trace(_playlist(), biases)
    assert trace["facts"]["biases"][0]["weak"] is True
    assert any("weak evidence" in line for line in trace["summary"])


def test_attach_and_context_roundtrip():
    pl = attach_decision_trace(_playlist(), biases=[{
        "kind": "artist", "key": "Berry Sakharof", "weight": 0.2,
        "sample_n": 3, "evidence": "e",
    }])
    assert "decision_trace" in pl
    ctx = playlists.context_from_playlist(pl)
    assert ctx["decision_trace"]["facts"]["biases"][0]["key"] == "Berry Sakharof"
    assert ctx["familiarity_constraint"] == "mixed"


if __name__ == "__main__":
    test_trace_matches_biases_and_marks_exploration_heuristic()
    test_trace_honest_when_no_artist_prefs()
    test_weak_evidence_called_out()
    test_attach_and_context_roundtrip()
    print("OK: all decision_trace tests passed")
