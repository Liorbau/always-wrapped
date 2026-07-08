"""Typed contracts for every LLM output boundary (Pydantic).

The models propose; these schemas are the shape-gate before code acts on the
proposals (the verifier/appliers then check the CONTENT against ground truth).
Validation failures mean "no usable proposal", never a crash.
"""

from typing import List, Optional

from pydantic import BaseModel, Field, ValidationError, field_validator

from logging_config import configure_logger

logger = configure_logger(__name__)


class Track(BaseModel):
    track_id: str = ""
    track_name: str = ""
    artist_name: str = ""
    duration_ms: Optional[int] = None
    familiarity: str = "?"
    reason: str = ""


class PlaylistProposal(BaseModel):
    name: str = "Untitled"
    description: str = ""
    target_duration_min: Optional[float] = Field(default=None, gt=0, lt=24 * 60)
    total_duration_min: Optional[float] = None
    familiarity_constraint: str = "mixed"
    tracks: List[Track] = []


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
