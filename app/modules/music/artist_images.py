"""Backfills artist artwork for legacy rows that predate the image column.

Spotify is only consulted for rows that are actually missing a URL: first one
batched id lookup, then a name search per straggler.
"""

from integrations.spotify import auth_connection
from core.logging import configure_logger

logger = configure_logger(__name__)

ARTIST_BATCH = 50
NAME_SEARCH_LIMIT = 5


def enrich_missing_images(artists, sp=None):
    missing = [row for row in artists if not row.get("artist_image_url")]
    if not missing:
        return artists

    client = sp or auth_connection()
    if client is None:
        logger.warning("Artist artwork backfill skipped: no Spotify client.")
        return artists

    images = _images_by_id(client, _unique_ids(missing))
    enriched = []
    for row in artists:
        url = row.get("artist_image_url") or images.get(row.get("artist_id"))
        if not url:
            url = _image_by_name(client, row.get("artist_name"), row.get("artist_id"))
        enriched.append(dict(row, artist_image_url=url))
    return enriched


def _unique_ids(rows):
    ids, seen = [], set()
    for row in rows:
        artist_id = row.get("artist_id")
        if artist_id and artist_id not in seen:
            seen.add(artist_id)
            ids.append(artist_id)
    return ids


def _first_image_url(artist):
    images = (artist or {}).get("images") or []
    return images[0]["url"] if images else None


def _images_by_id(sp, artist_ids):
    images = {}
    for start in range(0, len(artist_ids), ARTIST_BATCH):
        chunk = artist_ids[start : start + ARTIST_BATCH]
        try:
            response = sp.artists(chunk)
        except Exception as exc:
            logger.warning("Batch artist fetch failed: %s", exc)
            continue
        for artist in response.get("artists") or []:
            if artist:
                images[artist["id"]] = _first_image_url(artist)
    return images


def _image_by_name(sp, name, preferred_id):
    if not name or not str(name).strip():
        return None
    safe_name = str(name).strip().replace('"', "")
    try:
        response = sp.search(
            q=f'artist:"{safe_name}"', type="artist", limit=NAME_SEARCH_LIMIT
        )
    except Exception as exc:
        logger.warning("Artist search failed for %r: %s", name, exc)
        return None

    items = (response.get("artists") or {}).get("items") or []
    if not items:
        return None
    match = None
    if preferred_id:
        match = next((a for a in items if a.get("id") == preferred_id), None)
    if match is None:
        needle = safe_name.lower()
        match = next(
            (a for a in items if (a.get("name") or "").lower() == needle), items[0]
        )
    return _first_image_url(match)
