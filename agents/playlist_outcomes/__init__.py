"""Deterministic outcomes for DJ-pushed playlists (facts, not LLM math).

Attribution is "track played after push" — not proven playlist-sourced.
"""

from agents.playlist_outcomes.classify import SKIP_FRAC, classify_gaps
from agents.playlist_outcomes.queries import fetch_history_plays, last_bias_update_at
from agents.playlist_outcomes.score import outcome_for_playlist
from agents.playlist_outcomes.summary import (
    DISCLAIMER,
    aggregate_outcomes,
    cohort_rollups,
    learning_summary,
    observatory_line,
)

__all__ = [
    "SKIP_FRAC",
    "DISCLAIMER",
    "classify_gaps",
    "outcome_for_playlist",
    "learning_summary",
    "aggregate_outcomes",
    "cohort_rollups",
    "observatory_line",
    "fetch_history_plays",
    "last_bias_update_at",
]
