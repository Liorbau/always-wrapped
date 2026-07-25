"""The notifier seam: selection by env, and the vendor shape staying below it.

Runnable directly:  ./venv/bin/python tests/test_notifications.py
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from agents import notifications
from agents.notifications.base import Notifier
from agents.notifications.null import NullNotifier
from agents.notifications.telegram import TelegramNotifier


def _with_env(**values):
    previous = {k: os.environ.get(k) for k in values}

    def restore():
        for key, value in previous.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value

    for key, value in values.items():
        if value is None:
            os.environ.pop(key, None)
        else:
            os.environ[key] = value
    return restore


def test_env_selects_the_implementation():
    for choice, expected in (("telegram", TelegramNotifier), ("none", NullNotifier)):
        restore = _with_env(NOTIFIER=choice)
        notifications.reset_notifier()
        try:
            assert isinstance(notifications.get_notifier(), expected)
        finally:
            restore()
            notifications.reset_notifier()


def test_unknown_channel_fails_loudly():
    restore = _with_env(NOTIFIER="carrier-pigeon")
    notifications.reset_notifier()
    try:
        notifications.get_notifier()
    except ValueError as exc:
        assert "carrier-pigeon" in str(exc)
    else:
        raise AssertionError("an unknown NOTIFIER was accepted")
    finally:
        restore()
        notifications.reset_notifier()


def test_both_implementations_satisfy_the_protocol():
    for notifier in (TelegramNotifier(), NullNotifier()):
        assert isinstance(notifier, Notifier)


def test_null_notifier_is_silent_but_never_raises():
    notifier = NullNotifier()
    assert notifier.enabled() is False
    assert notifier.send_proposal({"title": "t", "start": "07:00"}, {}, "p1") is None
    assert notifier.send_message("someone", "hi") is False
    assert notifier.update_card(None, "text") is False


def test_telegram_is_a_no_op_without_a_token():
    restore = _with_env(TELEGRAM_BOT_TOKEN=None, TELEGRAM_CHAT_ID="42")
    try:
        notifier = TelegramNotifier()
        assert notifier.enabled() is False
        # no network, no exception — a missing channel must not break a run
        assert notifier.send_proposal({"title": "t", "start": "07:00"}, {}, "p1") is None
        assert notifier.send_message("42", "hi") is False
    finally:
        restore()


def test_telegram_proposal_wire_shape():
    """The callback_data contract the webhook parses back out must not drift."""
    import agents.notifications.telegram as telegram_module

    sent = {}

    class FakeResponse:
        def json(self):
            return {"ok": True, "result": {"message_id": 5, "chat": {"id": 42}}}

    original_post = telegram_module.requests.post
    telegram_module.requests.post = lambda url, json, timeout: (
        sent.update(url=url, payload=json), FakeResponse())[1]
    restore = _with_env(TELEGRAM_BOT_TOKEN="T", TELEGRAM_CHAT_ID="42")
    try:
        ref = TelegramNotifier().send_proposal(
            {"title": "Morning run", "start": "07:00"},
            {"name": "Run Fuel", "tracks": [{"track_name": "Go"}]}, "pid123")
        assert ref == {"chat_id": 42, "message_id": 5}
        assert "sendMessage" in sent["url"]
        buttons = sent["payload"]["reply_markup"]["inline_keyboard"][0]
        assert buttons[0]["callback_data"] == "approve:pid123"
        assert buttons[1]["callback_data"] == "reject:pid123"
    finally:
        telegram_module.requests.post = original_post
        restore()


def test_card_reference_is_opaque_to_callers():
    """Only the notifier reads its own card shape."""
    notifier = TelegramNotifier()
    ref = notifier._card_ref({"result": {"message_id": 7, "chat": {"id": 42}}})
    assert ref == {"chat_id": 42, "message_id": 7}
    assert notifier._card_ref({}) is None
    assert notifier._card_ref({"result": {}}) is None


if __name__ == "__main__":
    test_env_selects_the_implementation()
    test_unknown_channel_fails_loudly()
    test_both_implementations_satisfy_the_protocol()
    test_null_notifier_is_silent_but_never_raises()
    test_telegram_is_a_no_op_without_a_token()
    test_telegram_proposal_wire_shape()
    test_card_reference_is_opaque_to_callers()
    print("OK: all notification tests passed")
