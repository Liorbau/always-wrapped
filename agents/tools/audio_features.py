"""Audio features tool via ReccoBeats (free, no key) — the mood ground truth.

Spotify killed its audio-features API (Nov 2024); ReccoBeats serves the same
metrics for Spotify track ids: energy, valence (0=sad..1=happy), danceability,
tempo, acousticness, instrumentalness, speechiness, liveness, loudness.
Lets the DJ *check* mood instead of guessing, and gives
future verifiers a numeric handle on "energizing"/"sad".

Read-only third-party API; coverage is imperfect — missing tracks are reported
as missing, never invented.
"""

import json

import requests

from core.logging import configure_logger

logger = configure_logger(__name__)

API_URL = "https://api.reccobeats.com/v1/audio-features"
BATCH = 40
TIMEOUT_S = 10
KEEP = ("energy", "valence", "danceability", "tempo", "acousticness",
        "instrumentalness", "speechiness", "liveness", "loudness")


def get_audio_features(args):
    """Tool entrypoint: Spotify track ids -> mood metrics per id."""
    ids = [i for i in (args.get("track_ids") or []) if i]
    if not ids:
        return json.dumps({"error": "track_ids is required (list of Spotify ids)."})
    ids = list(dict.fromkeys(ids))[:100]

    features = {}
    try:
        for i in range(0, len(ids), BATCH):
            chunk = ids[i : i + BATCH]
            resp = requests.get(API_URL, params={"ids": ",".join(chunk)}, timeout=TIMEOUT_S)
            resp.raise_for_status()
            for item in resp.json().get("content") or []:
                # ReccoBeats uses its own ids; the Spotify id lives in href
                spotify_id = (item.get("href") or "").rsplit("/", 1)[-1]
                if spotify_id:
                    features[spotify_id] = {k: item.get(k) for k in KEEP}
    except requests.RequestException as exc:
        logger.warning("audio features fetch failed: %s", exc)
        return json.dumps({"error": f"ReccoBeats unavailable: {exc}"})

    missing = [i for i in ids if i not in features]
    logger.info("audio_features: %d found, %d missing", len(features), len(missing))
    return json.dumps({"features": features, "missing": missing})


AUDIO_FEATURES_SCHEMA = {
    "type": "function",
    "function": {
        "name": "get_audio_features",
        "description": (
            "Get mood/energy metrics for Spotify track ids (via ReccoBeats): "
            "energy 0-1, valence 0-1 (0=sad, 1=happy), danceability 0-1, "
            "tempo (BPM), acousticness 0-1, instrumentalness 0-1 (high = no "
            "vocals), speechiness 0-1 (high = spoken/rap), liveness 0-1 "
            "(high = live recording), loudness (dB, ~-60..0). USE THIS when "
            "the user names a mood - check candidates and drop tracks that "
            "contradict it (e.g. 'energizing' wants energy > ~0.6; 'sad' wants "
            "valence < ~0.4; 'focus/study' wants instrumentalness > ~0.5). "
            "Some tracks may be missing from the catalog - they come back in "
            "'missing'; judge those yourself."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "track_ids": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Spotify track ids (max 100).",
                }
            },
            "required": ["track_ids"],
        },
    },
}
