"""Typed contracts for every LLM output boundary (Pydantic).

The models propose; these schemas are the shape-gate before code acts on the
proposals (the verifier/appliers then check the CONTENT against ground truth).
Validation failures mean "no usable proposal", never a crash.
"""

from typing import List, Optional

from pydantic import BaseModel, Field, ValidationError, field_validator

from core.logging import configure_logger

logger = configure_logger(__name__)


class Track(BaseModel):
    track_id: str = ""
    track_name: str = ""
    artist_name: str = ""
    duration_ms: Optional[int] = None
    familiarity: str = "?"
    reason: str = ""


class Candidate(Track):
    """A pool entry the model curates; the packer (code) decides if it ships."""

    fit: float = 0.5     # 0..1 — how well it matches the request
    keep: bool = False   # pinned by a follow-up ("keep this one")

    @field_validator("fit", mode="before")
    @classmethod
    def _clamp_fit(cls, v):
        try:
            return min(1.0, max(0.0, float(v)))
        except (TypeError, ValueError):
            return 0.5


class PlaylistProposal(BaseModel):
    name: str = "Untitled"
    description: str = ""
    target_duration_min: Optional[float] = Field(default=None, gt=0, lt=24 * 60)
    total_duration_min: Optional[float] = None
    familiarity_constraint: str = "mixed"
    tracks: List[Track] = []          # legacy/final shape (packer output, old drafts)
    candidates: List[Candidate] = []  # the pool the packer assembles from


class BiasDelta(BaseModel):
    kind: str = Field(min_length=1, max_length=30)
    key: str = Field(min_length=1, max_length=120)
    delta: float
    evidence: str = ""

    @field_validator("kind", "key", "evidence", mode="before")
    @classmethod
    def _str(cls, v):
        return str(v).strip() if v is not None else ""

    @field_validator("evidence")
    @classmethod
    def _cap(cls, v):
        return v[:300]


class WrappedStyle(BaseModel):
    emoji: str = Field(default="🎧", max_length=8)


def parse_playlist(raw):
    """LLM playlist dict -> validated dict with defaults, or None."""
    if not raw:
        return None
    try:
        return PlaylistProposal.model_validate(raw).model_dump()
    except ValidationError as exc:
        logger.warning("Playlist proposal failed schema: %s", exc.errors()[:2])
        return None
