"""DJ agent tests — offline, scripted FakeLLM (no keys, no network).

Runnable directly:  ./venv/bin/python tests/test_dj.py
"""

import importlib
import json
import os
import sqlite3
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import agents.dj as dj_mod
from agents.dj import DJ_SYSTEM_PROMPT, request_playlist, verify_playlist
from tests.test_harness import FakeLLM, tool_call

PROPOSAL = {
    "thought": "verified constraints",
    "response": "Here is your afternoon playlist.",
    "satisfied": True,
    "playlist": {
        "name": "Afternoon Fuel",
        "description": "Energizing picks for 16-18 work",
        "total_duration_min": 44.5,
        "tracks": [
            {"track_id": "t1", "track_name": "Song A", "artist_name": "X",
             "duration_ms": 200000, "familiarity": "heavy", "reason": "peak-hours favorite"}
        ],
    },
}


def test_prompt_contains_critical_contracts():
    for needle in (
        "NEVER write to Spotify",   # HITL boundary
        "DATA from",                # untrusted-input fence
        "VERIFY with SQL",          # constraint verification loop
        "max 2 tracks per artist",
        "±25%",
        "playlist",
    ):
        assert needle in DJ_SYSTEM_PROMPT, f"prompt lost: {needle!r}"


def patched_verify(results):
    """Replace the DB verifier with a scripted sequence of violation lists."""
    seq = list(results)
    def _verify(playlist):
        return seq.pop(0) if len(seq) > 1 else seq[0]
    return _verify


def test_request_playlist_returns_proposal():
    llm = FakeLLM([
        tool_call("query_history", {"sql": "SELECT 1"}),
        {"content": json.dumps(PROPOSAL)},
    ])
    original = dj_mod.verify_playlist
    dj_mod.verify_playlist = patched_verify([[]])
    try:
        with tempfile.TemporaryDirectory() as tmp:
            out = request_playlist("energizing 45 min for work", llm=llm, max_steps=5, run_dir=tmp)
    finally:
        dj_mod.verify_playlist = original
    assert out["status"] == "satisfied"
    assert out["playlist"]["name"] == "Afternoon Fuel"
    assert out["playlist"]["tracks"][0]["track_id"] == "t1"
    assert out["response"] == "Here is your afternoon playlist."


def test_repair_loop_feeds_violations_back():
    """First proposal fails the code verifier; the DJ gets the violations and fixes them."""
    llm = FakeLLM([
        {"content": json.dumps(PROPOSAL)},                   # draft: fails verify
        {"content": json.dumps(dict(PROPOSAL, response="fixed"))},  # repair round
    ])
    original = dj_mod.verify_playlist
    dj_mod.verify_playlist = patched_verify([["3 tracks by X (max 2)"], []])
    try:
        with tempfile.TemporaryDirectory() as tmp:
            out = request_playlist("q", llm=llm, max_steps=5, run_dir=tmp)
    finally:
        dj_mod.verify_playlist = original
    assert out["status"] == "satisfied"
    assert out["playlist"] is not None
    assert out["violations"] == []
    assert out["response"] == "fixed"
    # the violation text reached the model as a user message
    assert llm.calls == 2


def test_verifier_catches_real_violations():
    """Pure verifier against a temp DB: artist cap, duration window, hallucinated id."""
    with tempfile.TemporaryDirectory() as tmp:
        path = os.path.join(tmp, "t.db")
        conn = sqlite3.connect(path)
        conn.execute("""CREATE TABLE listening_history (
            played_at TEXT PRIMARY KEY, track_id TEXT, track_name TEXT,
            artist_name TEXT, duration_ms INTEGER)""")
        rows = [(f"2026-07-01T10:00:0{i}Z", f"t{i}", f"Song {i}", "SameGuy", 200000) for i in range(3)]
        conn.executemany("INSERT INTO listening_history VALUES (?,?,?,?,?)", rows)
        conn.commit(); conn.close()

        original = dj_mod.get_db_connection
        original_sp = dj_mod._spotify_track_info
        dj_mod.get_db_connection = lambda readonly=False: (sqlite3.connect(path), "sqlite")
        dj_mod._spotify_track_info = lambda ids: {}  # offline: catalog knows nothing
        try:
            playlist = {
                "target_duration_min": 45,
                "tracks": [
                    {"track_id": "t0", "track_name": "Song 0"},
                    {"track_id": "t1", "track_name": "Song 1"},
                    {"track_id": "t2", "track_name": "Song 2"},
                    {"track_id": "ghost", "track_name": "Hallucinated"},
                ],
            }
            violations = verify_playlist(playlist)
        finally:
            dj_mod.get_db_connection = original
            dj_mod._spotify_track_info = original_sp

    text = " | ".join(violations)
    assert "ghost" in text                      # hallucinated id caught
    assert "3 tracks by SameGuy" in text        # artist cap caught
    assert "10.0 min" in text                   # real duration (3x200s) vs 45min target


def test_duration_miss_delivers_with_note():
    """Duration is a preference: a valid-but-short playlist ships with a note."""
    short = dict(PROPOSAL)
    short["playlist"] = {"name": "Short", "target_duration_min": 120,
                         "tracks": [{"track_id": "t1", "track_name": "Song A"}]}
    llm = FakeLLM([{"content": json.dumps(short)}])
    original_v, original_r = dj_mod.verify_playlist, dj_mod._reality
    dj_mod.verify_playlist = patched_verify([["real total duration is 3.3 min; ..."]])
    dj_mod._reality = lambda tracks: {"t1": {"artist": "X", "duration_ms": 200000, "plays": 5}}
    try:
        with tempfile.TemporaryDirectory() as tmp:
            out = request_playlist("2h of x", llm=llm, max_steps=3, run_dir=tmp)
    finally:
        dj_mod.verify_playlist, dj_mod._reality = original_v, original_r
    assert out["playlist"] is not None            # delivered, not withheld
    assert "Heads up" in out["note"]              # disclosed
    assert out["playlist"]["total_duration_min"] == 3.3


def test_sanitize_drops_ghosts_and_artist_extras():
    playlist = {"target_duration_min": 10, "tracks": [
        {"track_id": "a1"}, {"track_id": "a2"}, {"track_id": "a3"},  # same artist x3
        {"track_id": "ghost"},
    ]}
    original = dj_mod._reality
    dj_mod._reality = lambda tracks: {
        "a1": {"artist": "Same", "duration_ms": 300000, "plays": 1},
        "a2": {"artist": "Same", "duration_ms": 300000, "plays": 1},
        "a3": {"artist": "Same", "duration_ms": 300000, "plays": 1},
    }
    try:
        cleaned, note = dj_mod._sanitize(playlist)
    finally:
        dj_mod._reality = original
    ids = [t["track_id"] for t in cleaned["tracks"]]
    assert ids == ["a1", "a2"]                    # ghost dropped, artist cap enforced
    assert note is None                           # 10 min target, 10 min real: in window


def test_budget_death_salvages_verified_draft():
    """Steps ran out but a draft exists: sanitize and deliver it with a note."""
    draft = dict(PROPOSAL, satisfied=False)
    llm = FakeLLM([{"content": json.dumps(draft)}])
    original = dj_mod._reality
    dj_mod._reality = lambda tracks: {"t1": {"artist": "X", "duration_ms": 200000, "plays": 5}}
    try:
        with tempfile.TemporaryDirectory() as tmp:
            out = request_playlist("big request", llm=llm, max_steps=2, run_dir=tmp)
    finally:
        dj_mod._reality = original
    assert out["status"] == "max_steps_reached"
    assert out["playlist"] is not None           # draft salvaged, not discarded
    assert "step budget" in out["note"]


def test_verifier_enforces_never_constraint():
    playlist = {"target_duration_min": 10, "familiarity_constraint": "mostly_never",
                "tracks": [
                    {"track_id": "p1", "familiarity": "never", "track_name": "Lied About"},
                    {"track_id": "p2", "familiarity": "familiar", "track_name": "Old 1"},
                    {"track_id": "p3", "familiarity": "familiar", "track_name": "Old 2"},
                    {"track_id": "n1", "familiarity": "never", "track_name": "Fresh"},
                ]}
    original = dj_mod._reality
    dj_mod._reality = lambda tracks: {
        "p1": {"artist": "A", "duration_ms": 150000, "plays": 7},   # mislabeled!
        "p2": {"artist": "B", "duration_ms": 150000, "plays": 3},
        "p3": {"artist": "C", "duration_ms": 150000, "plays": 2},
        "n1": {"artist": "D", "duration_ms": 150000, "plays": 0},
    }
    try:
        text = " | ".join(dj_mod.verify_playlist(playlist))
        cleaned, _ = dj_mod._sanitize(playlist)
    finally:
        dj_mod._reality = original
    assert "labeled 'never' but has 7 plays" in text   # label honesty
    assert "must stay under 40%" in text               # mix enforcement
    # sanitize cuts played overflow: 4 tracks -> cap 1 played kept
    kept_ids = [t["track_id"] for t in cleaned["tracks"]]
    assert kept_ids == ["p1", "n1"]


def test_clarifying_question_delivered_not_crashed():
    """satisfied=true, playlist=null (the DJ asking a question) must return the
    question as an answer, never enter verify/repair (empty IN() crash)."""
    q = {"thought": "need duration", "response": "How long should it be?",
         "satisfied": True, "playlist": None}
    llm = FakeLLM([{"content": json.dumps(q)}])
    with tempfile.TemporaryDirectory() as tmp:
        out = request_playlist("make me a playlist", llm=llm, max_steps=3, run_dir=tmp)
    assert out["status"] == "satisfied"
    assert out["playlist"] is None
    assert out["response"] == "How long should it be?"


def test_unsatisfied_run_withholds_playlist():
    """No draft at all => withheld with a SPECIFIC, actionable explanation."""
    llm = FakeLLM([{"content": json.dumps({"thought": "", "response": "hmm",
                                           "satisfied": False})}])
    with tempfile.TemporaryDirectory() as tmp:
        out = request_playlist("impossible request", llm=llm, max_steps=2, run_dir=tmp)
    assert out["status"] == "max_steps_reached"
    assert out["playlist"] is None
    assert "step budget" in out["response"]      # explains what died
    assert "Ideas that usually work" in out["response"]  # and how to relax


if __name__ == "__main__":
    test_prompt_contains_critical_contracts()
    test_request_playlist_returns_proposal()
    test_repair_loop_feeds_violations_back()
    test_verifier_catches_real_violations()
    test_duration_miss_delivers_with_note()
    test_sanitize_drops_ghosts_and_artist_extras()
    test_budget_death_salvages_verified_draft()
    test_verifier_enforces_never_constraint()
    test_clarifying_question_delivered_not_crashed()
    test_unsatisfied_run_withholds_playlist()
    print("OK: all dj tests passed")
