"""Owner unlock for browser mutations that spend AI or write to Spotify.

Browse stays public. A correct OWNER_TOKEN sets an HttpOnly cookie for TTL_DAYS;
mutating routes require that cookie. Missing OWNER_TOKEN fails closed — no
token configured means no browser mutations, rather than an open door.

Telegram keeps its own webhook-secret + owner-ID checks and does not use this.
"""

import functools
import hmac
import os
from urllib.parse import urlparse

from flask import request
from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer

from app.errors import AppError, UNAUTHORIZED

COOKIE = "aw_owner"
TTL_DAYS = 7
TTL_SECONDS = TTL_DAYS * 24 * 60 * 60
_PAYLOAD = "owner"


def owner_token():
    return (os.getenv("OWNER_TOKEN") or "").strip()


def _serializer():
    secret = owner_token()
    if not secret:
        return None
    return URLSafeTimedSerializer(secret, salt="always-wrapped-owner")


def issue_cookie_value():
    serializer = _serializer()
    if serializer is None:
        raise AppError(
            UNAUTHORIZED,
            "Owner unlock is not configured (set OWNER_TOKEN).",
        )
    return serializer.dumps(_PAYLOAD)


def cookie_is_valid(value):
    serializer = _serializer()
    if serializer is None or not value:
        return False
    try:
        return serializer.loads(value, max_age=TTL_SECONDS) == _PAYLOAD
    except (BadSignature, SignatureExpired):
        return False


def is_unlocked():
    return cookie_is_valid(request.cookies.get(COOKIE))


def unlock(token):
    _reject_cross_origin()
    expected = owner_token()
    if not expected:
        raise AppError(
            UNAUTHORIZED,
            "Owner unlock is not configured (set OWNER_TOKEN).",
        )
    provided = (token or "").strip()
    if not provided or not hmac.compare_digest(provided, expected):
        raise AppError(UNAUTHORIZED, "Wrong password.")
    return issue_cookie_value()


def require_owner(view):
    """Decorator: reject the request unless the owner cookie is present."""

    @functools.wraps(view)
    def wrapped(*args, **kwargs):
        _reject_cross_origin()
        if not is_unlocked():
            raise AppError(
                UNAUTHORIZED,
                "Unlock the chat with the owner password first.",
            )
        return view(*args, **kwargs)

    return wrapped


def _reject_cross_origin():
    """Browser mutations must come from this origin (CSRF belt for cookie auth)."""
    origin = request.headers.get("Origin")
    if not origin:
        return
    host = request.host_url.rstrip("/")
    if urlparse(origin).netloc != urlparse(host).netloc:
        raise AppError(UNAUTHORIZED, "Cross-origin request rejected.")


def cookie_kwargs():
    return {
        "httponly": True,
        "samesite": "Lax",
        "secure": request.is_secure,
        "max_age": TTL_SECONDS,
        "path": "/",
    }
