"""Music module: layering seams, the error envelope, and insight rendering.

Runnable directly (no framework needed):  ./venv/bin/python tests/test_music.py
Also discoverable by pytest.
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from tests import sandbox  # noqa: F401  — must precede every app import

from app.errors import AppError, VALIDATION_ERROR, validation_error
from app.modules.music import artist_images, insight_service, mappers, search_service


def test_insight_mapper_escapes_untrusted_names():
    """Track/artist names are outside input; the card is rendered as HTML."""
    dto = mappers.insight_to_dto({
        "kind": "top_song", "icon": "music", "rank": 3,
        "track_name": "<script>alert(1)</script>",
        "artist_name": "A&B", "play_count": 12,
    })
    assert "<script>" not in dto["text"]
    assert "&lt;script&gt;" in dto["text"] and "A&amp;B" in dto["text"]
    assert "<b>#3</b>" in dto["text"] and dto["icon"] == "music"


def test_insight_mapper_covers_every_kind():
    for candidate in (
        {"kind": "top_song", "icon": "music", "rank": 1, "track_name": "S",
         "artist_name": "A", "play_count": 2},
        {"kind": "top_artist", "icon": "microphone", "rank": 2, "artist_name": "A",
         "play_count": 9},
        {"kind": "neglected_artist", "icon": "heart-crack", "artist_name": "A",
         "rank": 4, "variant": 1},
        {"kind": "peak_hour", "icon": "clock", "hour": 23, "label": "a night owl"},
        {"kind": "totals", "icon": "chart-bar", "plays": 5, "songs": 4, "artists": 3},
    ):
        dto = mappers.insight_to_dto(candidate)
        assert dto["text"] and dto["icon"] == candidate["icon"]


def test_insight_empty_state_is_explicit():
    assert mappers.insight_to_dto(None) == mappers.EMPTY_INSIGHT


def test_hour_label_boundaries():
    assert insight_service.hour_label(23) == "a night owl"
    assert insight_service.hour_label(4) == "a night owl"
    assert insight_service.hour_label(7) == "an early bird"
    assert insight_service.hour_label(12) == "a daytime listener"
    assert insight_service.hour_label(20) == "an evening viber"


def test_search_rank_parsing():
    assert search_service._as_rank("#12") == 12
    assert search_service._as_rank(" 7 ") == 7
    assert search_service._as_rank("radiohead") is None
    assert search_service._by_rank(0, "all_time") == []


def test_search_by_text_matches_track_or_artist():
    songs = [
        {"track_name": "Creep", "artist_name": "Radiohead", "play_count": 9},
        {"track_name": "Nude", "artist_name": "Radiohead", "play_count": 4},
        {"track_name": "Alright", "artist_name": "Kendrick", "play_count": 3},
    ]
    original = (search_service.repository.songs_by_rank,
                search_service.repository.artists_by_rank)
    search_service.repository.songs_by_rank = lambda tr, offset=None: songs
    search_service.repository.artists_by_rank = lambda tr, offset=None: []
    try:
        hits = search_service.search("radiohead")
    finally:
        (search_service.repository.songs_by_rank,
         search_service.repository.artists_by_rank) = original
    assert [h["track_name"] for h in hits] == ["Creep", "Nude"]
    assert [h["rank"] for h in hits] == [1, 2]
    assert all(h["type"] == "song" for h in hits)


class FakeSpotify:
    def __init__(self):
        self.batches = []

    def artists(self, ids):
        self.batches.append(list(ids))
        return {"artists": [{"id": i, "images": [{"url": f"http://img/{i}"}]} for i in ids]}

    def search(self, q, type, limit):
        return {"artists": {"items": [{"name": "Nameless", "images": []}]}}


def test_enrichment_skips_spotify_when_nothing_missing():
    sp = FakeSpotify()
    rows = [{"artist_name": "A", "play_count": 1, "artist_image_url": "http://have"}]
    assert artist_images.enrich_missing_images(rows, sp=sp) is rows
    assert sp.batches == []


def test_enrichment_batches_ids_within_the_api_limit():
    sp = FakeSpotify()
    rows = [{"artist_name": f"A{i}", "play_count": 1, "artist_id": f"id{i}",
             "artist_image_url": None} for i in range(120)]
    enriched = artist_images.enrich_missing_images(rows, sp=sp)
    assert [len(b) for b in sp.batches] == [50, 50, 20]
    assert enriched[0]["artist_image_url"] == "http://img/id0"
    assert len(enriched) == 120


def test_error_envelope_shape():
    payload = validation_error("bad range", {"start": "x"}).to_payload()
    assert payload == {"error": {"code": VALIDATION_ERROR, "message": "bad range",
                                 "details": {"start": "x"}}}
    assert validation_error("x").status == 400
    assert AppError("NOT_FOUND", "gone").status == 404


def test_wrapped_custom_range_is_validated_at_the_edge():
    from app.modules.wrapped.orchestrators import build_edition

    for start, end in (("2026-01-01", None), ("nope", "2026-01-02"),
                       ("2026-02-02", "2026-01-01")):
        try:
            build_edition.execute(period="custom", start=start, end=end)
        except AppError as exc:
            assert exc.code == VALIDATION_ERROR and exc.status == 400
        else:
            raise AssertionError(f"accepted invalid range {start}..{end}")


if __name__ == "__main__":
    test_insight_mapper_escapes_untrusted_names()
    test_insight_mapper_covers_every_kind()
    test_insight_empty_state_is_explicit()
    test_hour_label_boundaries()
    test_search_rank_parsing()
    test_search_by_text_matches_track_or_artist()
    test_enrichment_skips_spotify_when_nothing_missing()
    test_enrichment_batches_ids_within_the_api_limit()
    test_error_envelope_shape()
    test_wrapped_custom_range_is_validated_at_the_edge()
    print("OK: all music tests passed")
