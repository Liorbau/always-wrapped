"""DJ agent tests — offline, scripted FakeLLM (no keys, no network).

Runnable directly:  ./venv/bin/python tests/test_dj.py
"""

import json
import os
import sqlite3
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from agents.dj import DJ_SYSTEM_PROMPT, request_playlist, verify_playlist
from agents.dj import candidates, ground_truth, packer, verifier
from tests.test_harness import FakeLLM, tool_call

# a valid pool: 12 tracks x 4min = 48min against a 45min target (window 33.8-56.2)
POOL = {
    "thought": "gathered",
    "response": "Here is your afternoon playlist.",
    "satisfied": True,
    "playlist": {
        "name": "Afternoon Fuel",
        "description": "Energizing picks",
        "target_duration_min": 45,
        "familiarity_constraint": "mixed",
        "candidates": [
            {"track_id": f"t{i}", "track_name": f"Song {i}", "artist_name": f"A{i}",
             "fit": 0.9 - i * 0.01, "reason": "fits"} for i in range(12)
        ],
    },
}


def pool_reality(n=12, dur=240000, plays=5, artist=None):
    return {f"t{i}": {"artist": artist or f"A{i}", "duration_ms": dur, "plays": plays}
            for i in range(n)}


def with_reality(reality, fn):
    original = ground_truth.reality
    ground_truth.reality = lambda tracks: reality
    try:
        return fn()
    finally:
        ground_truth.reality = original


def test_prompt_contains_critical_contracts():
    for needle in (
        "NEVER write to Spotify",     # HITL boundary
        "DATA from",                  # untrusted-input fence
        "CANDIDATE POOL",             # the packer contract
        "Duration arithmetic is NOT your job",
        "keep:true",                  # follow-up pins
        "±25%",
        "candidates",
    ):
        assert needle in DJ_SYSTEM_PROMPT, f"prompt lost: {needle!r}"


# --- packer unit tests (pure function + patched reality) ---------------------

def test_pack_hits_duration_window():
    packed, gap = with_reality(pool_reality(), lambda: packer.pack(POOL["playlist"]))
    assert gap == 0
    assert 33.8 <= packed["total_duration_min"] <= 56.2
    assert packed["name"] == "Afternoon Fuel"
    assert all(t["duration_ms"] == 240000 for t in packed["tracks"])


def test_pack_enforces_artist_cap():
    packed, gap = with_reality(
        pool_reality(artist="Same"), lambda: packer.pack(POOL["playlist"]))
    assert len(packed["tracks"]) == 2            # only 2 per artist usable
    assert gap > 0                               # which leaves a supply gap


def test_pack_enforces_never_mix_and_corrects_labels():
    pl = dict(POOL["playlist"], familiarity_constraint="mostly_never")
    reality = pool_reality(plays=0)
    for i in (0, 1, 2, 3):                       # 4 of 12 are actually played
        reality[f"t{i}"]["plays"] = 9
    packed, _ = with_reality(reality, lambda: packer.pack(pl))
    played = [t for t in packed["tracks"] if t["familiarity"] != "never"]
    assert len(played) / len(packed["tracks"]) <= 0.4
    assert all(t["familiarity"] in ("never", "familiar") for t in packed["tracks"])


def test_pack_honors_pins_first():
    pl = json.loads(json.dumps(POOL["playlist"]))
    pl["candidates"][-1]["keep"] = True          # worst-fit track, pinned
    pl["target_duration_min"] = 8                # room for only 2 tracks
    packed, _ = with_reality(pool_reality(), lambda: packer.pack(pl))
    assert "t11" in [t["track_id"] for t in packed["tracks"]]


def test_pack_drops_ghosts_dupes_and_reports_shortfall():
    pl = {"target_duration_min": 45, "candidates": [
        {"track_id": "t0", "fit": 0.9}, {"track_id": "t0", "fit": 0.9},  # dupe
        {"track_id": "ghost", "fit": 1.0},                               # nowhere
    ]}
    packed, gap = with_reality(pool_reality(n=1), lambda: packer.pack(pl))
    assert [t["track_id"] for t in packed["tracks"]] == ["t0"]
    assert gap > 30                              # 4min of 45 -> big shortfall


def test_pack_interleaves_never_tracks():
    pl = dict(POOL["playlist"], familiarity_constraint="mixed")
    reality = pool_reality(plays=5)
    for i in (0, 1, 2):                          # top-fit tracks are never-played
        reality[f"t{i}"]["plays"] = 0
    packed, _ = with_reality(reality, lambda: packer.pack(pl))
    first_three = [t["familiarity"] for t in packed["tracks"][:3]]
    assert first_three.count("never") < 3        # not front-loaded


def test_pack_accepts_legacy_tracks_key():
    pl = {"target_duration_min": 8,
          "tracks": [{"track_id": "t0"}, {"track_id": "t1"}]}
    packed, gap = with_reality(pool_reality(n=2), lambda: packer.pack(pl))
    assert len(packed["tracks"]) == 2 and gap == 0


# --- flow tests ---------------------------------------------------------------

def test_request_playlist_packs_a_proposal():
    llm = FakeLLM([
        tool_call("query_history", {"sql": "SELECT 1"}),
        {"content": json.dumps(POOL)},
    ])
    def go():
        return request_playlist("energizing 45 min", llm=llm, max_steps=5)
    out = with_reality(pool_reality(), go)
    assert out["status"] == "satisfied"
    assert out["violations"] == []
    assert out["playlist"]["name"] == "Afternoon Fuel"
    assert 33.8 <= out["playlist"]["total_duration_min"] <= 56.2
    assert out["note"] is None


def test_supply_loop_merges_incremental_candidates():
    """Pool too small -> supply message -> reply with ONLY new entries -> merged."""
    small = json.loads(json.dumps(POOL))
    small["playlist"]["candidates"] = small["playlist"]["candidates"][:3]  # 12min of 45
    increment = json.loads(json.dumps(POOL))
    increment["playlist"]["candidates"] = increment["playlist"]["candidates"][3:]  # new only
    llm = FakeLLM([
        {"content": json.dumps(small)},
        {"content": json.dumps(increment)},
    ])
    def go():
        return request_playlist("45 min", llm=llm, max_steps=5)
    out = with_reality(pool_reality(), go)
    assert llm.calls == 2                        # exactly one supply round
    assert out["playlist"] is not None and out["note"] is None
    assert out["playlist"]["total_duration_min"] >= 33.8  # merged pool filled the window


def test_exhausted_supply_delivers_short_with_note():
    """Model can't supply enough even after rounds -> deliver best with a note."""
    small = json.loads(json.dumps(POOL))
    small["playlist"]["candidates"] = small["playlist"]["candidates"][:3]
    llm = FakeLLM([{"content": json.dumps(small)}])   # repeats forever
    original_gc = candidates.gap_candidates
    candidates.gap_candidates = lambda *a, **k: []       # history has nothing either
    def go():
        return request_playlist("45 min", llm=llm, max_steps=9)
    try:
        out = with_reality(pool_reality(n=3), go)
    finally:
        candidates.gap_candidates = original_gc
    assert out["playlist"] is not None           # delivered, not withheld
    assert "Heads up" in out["note"]
    assert out["playlist"]["total_duration_min"] == 12.0


def test_reserve_topup_closes_gap_from_history():
    """Model supplies too little even after rounds -> code tops up from history."""
    small = json.loads(json.dumps(POOL))
    small["playlist"]["candidates"] = small["playlist"]["candidates"][:3]  # 12 of 45 min
    llm = FakeLLM([{"content": json.dumps(small)}])   # lazy forever
    reality = pool_reality()                          # t3..t11 exist in "history"
    original_gc = candidates.gap_candidates
    candidates.gap_candidates = lambda exclude, limit=60, hebrew_only=False: [
        f"t{i} | Song {i} — A{i} | 240000 | 6 plays | pop" for i in range(3, 12)]
    def go():
        return request_playlist("45 min", llm=llm, max_steps=9)
    try:
        out = with_reality(reality, go)
    finally:
        candidates.gap_candidates = original_gc
    assert out["playlist"] is not None
    assert out["note"] is None                        # gap fully closed
    assert out["playlist"]["total_duration_min"] >= 33.8
    reasons = [t["reason"] for t in out["playlist"]["tracks"]]
    assert any("reserve" in r for r in reasons)       # history reserve was used


def test_budget_death_salvages_draft_pool():
    draft = dict(POOL, satisfied=False)
    llm = FakeLLM([{"content": json.dumps(draft)}])
    def go():
        return request_playlist("big request", llm=llm, max_steps=2)
    out = with_reality(pool_reality(), go)
    assert out["status"] == "max_steps_reached"
    assert out["playlist"] is not None           # pool packed anyway
    assert "step budget" in out["note"]


def test_clarifying_question_delivered_not_crashed():
    q = {"thought": "need duration", "response": "How long should it be?",
         "satisfied": True, "playlist": None}
    llm = FakeLLM([{"content": json.dumps(q)}])
    out = request_playlist("make me a playlist", llm=llm, max_steps=3)
    assert out["status"] == "satisfied"
    assert out["playlist"] is None
    assert out["response"] == "How long should it be?"


def test_unsatisfied_run_withholds_playlist():
    llm = FakeLLM([{"content": json.dumps({"thought": "", "response": "hmm",
                                           "satisfied": False})}])
    out = request_playlist("impossible request", llm=llm, max_steps=2)
    assert out["status"] == "max_steps_reached"
    assert out["playlist"] is None
    assert "step budget" in out["response"]
    assert "Ideas that usually work" in out["response"]


# --- verifier stays as the independent invariant check ------------------------

def test_verifier_catches_real_violations():
    with tempfile.TemporaryDirectory() as tmp:
        path = os.path.join(tmp, "t.db")
        conn = sqlite3.connect(path)
        conn.execute("""CREATE TABLE listening_history (
            played_at TEXT PRIMARY KEY, track_id TEXT, track_name TEXT,
            artist_name TEXT, duration_ms INTEGER)""")
        rows = [(f"2026-07-01T10:00:0{i}Z", f"t{i}", f"Song {i}", "SameGuy", 200000)
                for i in range(3)]
        conn.executemany("INSERT INTO listening_history VALUES (?,?,?,?,?)", rows)
        conn.commit(); conn.close()

        original = ground_truth.get_db_connection
        original_sp = ground_truth.spotify_track_info
        ground_truth.get_db_connection = lambda readonly=False: (sqlite3.connect(path), "sqlite")
        ground_truth.spotify_track_info = lambda ids: {}
        try:
            playlist = {"target_duration_min": 45, "tracks": [
                {"track_id": "t0", "track_name": "Song 0"},
                {"track_id": "t1", "track_name": "Song 1"},
                {"track_id": "t2", "track_name": "Song 2"},
                {"track_id": "ghost", "track_name": "Hallucinated"},
            ]}
            violations = verify_playlist(playlist)
        finally:
            ground_truth.get_db_connection = original
            ground_truth.spotify_track_info = original_sp

    text = " | ".join(violations)
    assert "ghost" in text
    assert "3 tracks by SameGuy" in text
    assert "10.0 min" in text


def test_verifier_enforces_never_constraint():
    playlist = {"target_duration_min": 10, "familiarity_constraint": "mostly_never",
                "tracks": [
                    {"track_id": "p1", "familiarity": "never", "track_name": "Lied About"},
                    {"track_id": "p2", "familiarity": "familiar", "track_name": "Old 1"},
                    {"track_id": "p3", "familiarity": "familiar", "track_name": "Old 2"},
                    {"track_id": "n1", "familiarity": "never", "track_name": "Fresh"},
                ]}
    reality = {
        "p1": {"artist": "A", "duration_ms": 150000, "plays": 7},   # mislabeled!
        "p2": {"artist": "B", "duration_ms": 150000, "plays": 3},
        "p3": {"artist": "C", "duration_ms": 150000, "plays": 2},
        "n1": {"artist": "D", "duration_ms": 150000, "plays": 0},
    }
    def go():
        text = " | ".join(verify_playlist(playlist))
        cleaned, _ = verifier.sanitize(playlist)
        return text, cleaned
    text, cleaned = with_reality(reality, go)
    assert "labeled 'never' but has 7 plays" in text
    assert "must stay under 40%" in text
    kept_ids = [t["track_id"] for t in cleaned["tracks"]]
    assert kept_ids == ["p1", "n1"]


if __name__ == "__main__":
    test_prompt_contains_critical_contracts()
    test_pack_hits_duration_window()
    test_pack_enforces_artist_cap()
    test_pack_enforces_never_mix_and_corrects_labels()
    test_pack_honors_pins_first()
    test_pack_drops_ghosts_dupes_and_reports_shortfall()
    test_pack_interleaves_never_tracks()
    test_pack_accepts_legacy_tracks_key()
    test_request_playlist_packs_a_proposal()
    test_supply_loop_merges_incremental_candidates()
    test_reserve_topup_closes_gap_from_history()
    test_exhausted_supply_delivers_short_with_note()
    test_budget_death_salvages_draft_pool()
    test_clarifying_question_delivered_not_crashed()
    test_unsatisfied_run_withholds_playlist()
    test_verifier_catches_real_violations()
    test_verifier_enforces_never_constraint()
    print("OK: all dj tests passed")
