"""Timezone resolution for browser-supplied IANA names.

Runnable directly:  ./venv/bin/python tests/test_timezone.py
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from tests import sandbox  # noqa: F401

from core.timezone import resolve_tz


def test_resolve_tz_prefers_valid_client_value():
    assert resolve_tz("Europe/London") == "Europe/London"


def test_resolve_tz_falls_back_when_client_value_is_invalid():
    original = os.environ.get("USER_TZ")
    os.environ["USER_TZ"] = "Asia/Jerusalem"
    try:
        assert resolve_tz("Not/AZone") == "Asia/Jerusalem"
    finally:
        if original is None:
            os.environ.pop("USER_TZ", None)
        else:
            os.environ["USER_TZ"] = original


def test_resolve_tz_uses_user_tz_when_client_omits():
    original = os.environ.get("USER_TZ")
    os.environ["USER_TZ"] = "America/New_York"
    try:
        assert resolve_tz(None) == "America/New_York"
        assert resolve_tz("") == "America/New_York"
    finally:
        if original is None:
            os.environ.pop("USER_TZ", None)
        else:
            os.environ["USER_TZ"] = original


if __name__ == "__main__":
    test_resolve_tz_prefers_valid_client_value()
    test_resolve_tz_falls_back_when_client_value_is_invalid()
    test_resolve_tz_uses_user_tz_when_client_omits()
    print("OK: all timezone tests passed")
