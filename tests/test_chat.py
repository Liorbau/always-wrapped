"""Chat backend tests: router, ledger, HITL push, endpoint flow — all offline.

Runnable directly:  ./venv/bin/python tests/test_chat.py
"""

import contextlib
import json
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from tests import sandbox  # noqa: F401  — must precede every app import

os.environ.setdefault("OWNER_TOKEN", "test-owner-secret")

from agents import notifications
from agents.router import route_message
from integrations.spotify import push_playlist
from agents.store import hitl
from app.modules.agent_api import planning, proposals, runner, runs, sessions
from app.modules.agent_api.orchestrators import send_chat, trigger_evaluator
from tests.test_harness import FakeLLM
from tests.test_store import temp_db

import server


def unlocked_client():
    """Browser mutations require the owner cookie; Telegram tests skip this."""
    client = server.app.test_client()
    unlocked = client.post("/api/owner/unlock", json={"token": os.environ["OWNER_TOKEN"]})
    assert unlocked.status_code == 200, unlocked.get_json()
    return client


class RecordingNotifier:
    """Stand-in for any push channel — records instead of reaching the network."""

    name = "recording"

    def __init__(self):
        self.proposals = []
        self.messages = []

    def enabled(self):
        return True

    def send_proposal(self, block, playlist, proposal_id, recipient=None):
        self.proposals.append(proposal_id)
        return {"card": proposal_id}

    def send_message(self, recipient, text):
        self.messages.append((recipient, text))
        return True

    def acknowledge(self, interaction_id, text=""):
        return True

    def update_card(self, card_ref, text):
        return True


@contextlib.contextmanager
def recording_notifier():
    notifier = notifications.set_notifier(RecordingNotifier())
    try:
        yield notifier
    finally:
        notifications.reset_notifier()


@contextlib.contextmanager
def patched(*targets):
    """Temporarily set (module, attribute, value) triples; always restore."""
    originals = [(obj, name, getattr(obj, name)) for obj, name, _ in targets]
    for obj, name, value in targets:
        setattr(obj, name, value)
    try:
        yield
    finally:
        for obj, name, value in originals:
            setattr(obj, name, value)


def test_router_classifies_and_falls_back():
    llm = FakeLLM([{"content": '{"route": "off_topic", "satisfied": true}'}])
    assert route_message("give me a cake recipe", llm=llm) == "off_topic"
    llm = FakeLLM([{"content": '{"route": "playlist_request", "satisfied": true}'}])
    assert route_message("build me a workout mix", llm=llm) == "playlist_request"
    llm = FakeLLM([{"content": '{"route": "plan_day", "satisfied": true}'}])
    assert route_message("plan my day", llm=llm) == "plan_day"
    # garbage output falls back to the safe read-only route
    llm = FakeLLM([{"content": "not json at all"}])
    assert route_message("what did I play?", llm=llm) == "data_question"


def test_router_followup_context():
    llm = FakeLLM([{"content": '{"route": "playlist_request", "satisfied": true}'}])
    r = route_message("how for example?", llm=llm,
                      context=("build me a 2h hebrew playlist", "playlist_request"))
    assert r == "playlist_request"


class FakePushSpotify:
    def __init__(self):
        self.added = None
        self.description = None

    def current_user(self):
        return {"id": "lior"}

    def user_playlist_create(self, user_id, name, public, description):
        assert public is False, "playlists must be private"
        self.description = description
        return {"id": "pl1", "external_urls": {"spotify": "https://spotify/pl1"}}

    def playlist_add_items(self, playlist_id, ids):
        self.added = (playlist_id, ids)


def test_push_playlist_private_with_ids():
    sp = FakePushSpotify()
    out = push_playlist(
        {"name": "Mix", "description": "d", "tracks": [{"track_id": "t1"}, {"track_id": "t2"}]},
        sp=sp,
    )
    assert out["url"] == "https://spotify/pl1"
    assert sp.added == ("pl1", ["t1", "t2"])
    assert sp.description == "d — built by the Always-Wrapped DJ, just for you."
    assert push_playlist({"tracks": []}, sp=sp)["error"]


def test_push_playlist_description_respects_spotify_limit():
    """A long DJ description must not push the signature past Spotify's 300."""
    sp = FakePushSpotify()
    push_playlist(
        {"name": "Mix", "description": "x" * 500, "tracks": [{"track_id": "t1"}]},
        sp=sp,
    )
    assert len(sp.description) == 300
    assert sp.description.endswith("just for you.")


def _poll(client, run_id, timeout=5.0):
    deadline = time.time() + timeout
    while time.time() < deadline:
        r = client.get(f"/api/agent/run/{run_id}").get_json()
        if r.get("done"):
            return r
        time.sleep(0.02)
    raise AssertionError("run never finished")


def test_endpoint_flow_propose_approve_reject():
    from agents.dj import ground_truth, verifier

    client = unlocked_client()
    pushed = []
    proposal_json = json.dumps({
        "thought": "t", "response": "here you go", "satisfied": True,
        "playlist": {"name": "Mix", "target_duration_min": 45,
                     "candidates": [{"track_id": "t1", "fit": 0.9}]}})
    real_build_dj, real_build_analyst = runner.build_dj, runner.build_analyst

    with temp_db(), patched(
        (send_chat, "budget_left", lambda: 1.0),
        (send_chat, "route_message", lambda m, context=None: {
            "cake": "off_topic", "mix": "playlist_request"}.get(m, "data_question")),
        (runner, "get_client", lambda provider=None, model=None: FakeLLM([
            {"content": proposal_json}])),
        (runner, "build_dj", real_build_dj),
        (runner, "build_analyst", real_build_analyst),
        (proposals, "push_playlist", lambda pl: (pushed.append(pl) or
                                                 {"playlist_id": "pl1", "url": "u",
                                                  "track_count": 1})),
        (verifier, "verify_playlist", lambda pl: []),
        (ground_truth, "reality", lambda tracks: {
            "t1": {"artist": "X", "duration_ms": 45 * 60000, "plays": 5}}),
    ):
        try:
            # off-topic refused synchronously, no run started
            r = client.post("/api/agent/chat", json={"message": "cake"})
            assert r.get_json()["type"] == "refusal" and r.status_code == 200

            # playlist request -> 202 + run_id -> poll to proposal; nothing pushed
            r = client.post("/api/agent/chat", json={"message": "mix", "session_id": "s1"})
            assert r.status_code == 202
            body = r.get_json()
            assert body["type"] == "run_started"
            assert body["route"] == "playlist_request" and body["session_id"] == "s1"
            result = _poll(client, body["run_id"])["result"]
            assert result["type"] == "playlist_proposal" and not pushed
            pid = result["proposal_id"]

            # multi-turn: same session reuses the SAME dj harness object
            dj_first = sessions.SESSIONS["s1"]["dj"]
            r2 = client.post("/api/agent/chat", json={"message": "mix", "session_id": "s1"})
            _poll(client, r2.get_json()["run_id"])
            assert sessions.SESSIONS["s1"]["dj"] is dj_first

            # provider switch resets the session (fresh conversation)
            r3 = client.post("/api/agent/chat",
                             json={"message": "mix", "session_id": "s1", "provider": "anthropic"})
            _poll(client, r3.get_json()["run_id"])
            assert sessions.SESSIONS["s1"]["dj"] is not dj_first

            # approve -> exactly one push, proposal consumed
            r = client.post("/api/agent/approve", json={"proposal_id": pid}).get_json()
            assert r["type"] == "pushed" and len(pushed) == 1
            repeat = client.post("/api/agent/approve", json={"proposal_id": pid})
            assert repeat.status_code == 404
            assert repeat.get_json()["error"]["code"] == "NOT_FOUND"

            # reject with reason -> logged for the Evaluator, never pushed
            pid2 = _poll(client, client.post(
                "/api/agent/chat", json={"message": "mix", "session_id": "s1"}
            ).get_json()["run_id"])["result"]["proposal_id"]
            r = client.post("/api/agent/reject",
                            json={"proposal_id": pid2, "reason": "too mellow"}).get_json()
            assert r["type"] == "rejected" and len(pushed) == 1
            [logged] = hitl.recent(hitl.REJECTED)
            assert logged["reason"] == "too mellow"

            # empty message is rejected at the edge with the shared envelope
            bad = client.post("/api/agent/chat", json={"message": "   "})
            assert bad.status_code == 400
            assert bad.get_json()["error"]["code"] == "VALIDATION_ERROR"

            # budget exhausted -> 429
            send_chat.budget_left = lambda: -0.01
            over = client.post("/api/agent/chat", json={"message": "mix"})
            assert over.status_code == 429
            assert over.get_json()["error"]["code"] == "BUDGET_EXHAUSTED"
        finally:
            sessions.clear()
            runs.clear()
            proposals.clear()


def test_observatory_endpoints():
    client = server.app.test_client()
    assert client.get("/agents").status_code == 200
    r = client.get("/api/agent/activity").get_json()
    assert set(r) == {
        "active", "events", "daily_cost", "week_cost", "month_cost", "daily_budget",
    }
    assert r["active"] is None or "agent" in r["active"]


def test_commands_dictionary_and_help():
    from agents.commands import as_dicts, help_text
    from agents import timers

    web = {c["cmd"] for c in as_dicts("web")}
    assert web == {"/help", "/spend", "/plantime"}
    tg = {c["cmd"] for c in as_dicts("telegram")}
    assert "/timer" in tg and "/spend" not in tg
    assert "/plantime" in help_text("web") and "/spend" in help_text("web")
    assert timers.USAGE == help_text("telegram")

    client = server.app.test_client()
    r = client.get("/api/agent/commands?surface=web").get_json()
    assert r["type"] == "commands"
    assert {c["cmd"] for c in r["commands"]} == web

    unlocked = unlocked_client()
    help_reply = unlocked.post("/api/agent/chat", json={"message": "/help"}).get_json()
    assert help_reply["type"] == "commands"
    assert "/spend" in help_reply["response"]


def test_spend_chat_command_and_route():
    client = unlocked_client()
    with temp_db(), patched(
        (send_chat, "route_message", lambda m, context=None: "spend_inquiry"),
        (send_chat, "budget_left", lambda: -0.01),
    ):
        from agents.store import run_costs
        run_costs.record("r1", 1.25)
        cmd = client.post("/api/agent/chat", json={"message": "/spend"})
        assert cmd.status_code == 200
        body = cmd.get_json()
        assert body["type"] == "spend"
        assert "LLM spend" in body["response"]
        assert body["today"] == 1.25

        # Natural-language spend inquiry still answers when agents are over budget
        nl = client.post("/api/agent/chat", json={"message": "how much did the AI cost?"})
        assert nl.status_code == 200 and nl.get_json()["type"] == "spend"


def test_unknown_run_uses_the_error_envelope():
    client = server.app.test_client()
    r = client.get("/api/agent/run/does-not-exist")
    assert r.status_code == 404
    assert r.get_json()["error"] == {"code": "NOT_FOUND", "message": "Unknown run.",
                                     "details": {}}


def test_evaluator_trigger_endpoint():
    client = unlocked_client()
    fake_harness = type("H", (), {"event_hook": None, "trajectory": [],
                                  "metadata": {"cost_usd": 0}})()
    with patched(
        (trigger_evaluator, "budget_left", lambda: 1.0),
        (trigger_evaluator, "build_evaluator", lambda: fake_harness),
        (runner, "run_evaluator", lambda harness=None: {"report": "learned stuff",
                                                        "applied": 2, "cost_usd": 0.01}),
    ):
        try:
            r = client.post("/api/agent/evaluate")
            assert r.status_code == 202
            done = _poll(client, r.get_json()["run_id"], timeout=3)
            assert done["result"]["response"] == "learned stuff"
            feed = client.get("/api/agent/activity").get_json()["events"]
            assert any("learned 2 preference" in e["text"] for e in feed)
        finally:
            runs.clear()


def test_telegram_webhook_secret_and_actions():
    """The webhook is a write trigger — secret gates it; approve pushes, reject discards."""
    client = server.app.test_client()
    pushed = []
    os.environ["TELEGRAM_WEBHOOK_SECRET"] = "s3cr3t"
    os.environ["TELEGRAM_CHAT_ID"] = "42"  # owner id for the callback owner-check
    os.environ.pop("TELEGRAM_BOT_TOKEN", None)  # telegram calls no-op (no network)

    def cb(pid, action, uid=42):
        return {"callback_query": {"id": "c1", "from": {"id": uid},
                                   "data": f"{action}:{pid}"}}

    with temp_db(), patched(
        (proposals, "push_playlist", lambda pl: (pushed.append(pl) or {"url": "u"})),
    ):
        try:
            # wrong secret -> 403, nothing touched
            proposals.PENDING["p1"] = {"name": "A", "tracks": [{"track_id": "t1"}]}
            r = client.post("/api/agent/telegram/webhook", json=cb("p1", "approve"),
                            headers={"X-Telegram-Bot-Api-Secret-Token": "wrong"})
            assert r.status_code == 403 and not pushed and "p1" in proposals.PENDING
            assert r.get_json()["error"]["code"] == "FORBIDDEN"

            # right secret but a non-owner tapper -> ignored, nothing pushed
            r = client.post("/api/agent/telegram/webhook", json=cb("p1", "approve", uid=999),
                            headers={"X-Telegram-Bot-Api-Secret-Token": "s3cr3t"})
            assert r.status_code == 200 and not pushed and "p1" in proposals.PENDING

            # right secret + approve -> pushed once, proposal consumed
            r = client.post("/api/agent/telegram/webhook", json=cb("p1", "approve"),
                            headers={"X-Telegram-Bot-Api-Secret-Token": "s3cr3t"})
            assert r.status_code == 200 and len(pushed) == 1
            assert "p1" not in proposals.PENDING

            # right secret + reject -> discarded + logged, no extra push
            proposals.PENDING["p2"] = {"name": "B", "tracks": []}
            r = client.post("/api/agent/telegram/webhook", json=cb("p2", "reject"),
                            headers={"X-Telegram-Bot-Api-Secret-Token": "s3cr3t"})
            assert r.status_code == 200 and len(pushed) == 1
            assert "p2" not in proposals.PENDING
            [logged] = hitl.recent(hitl.REJECTED)
            assert logged["playlist"]["name"] == "B"
        finally:
            os.environ.pop("TELEGRAM_WEBHOOK_SECRET", None)
            os.environ.pop("TELEGRAM_CHAT_ID", None)
            proposals.clear()


def test_plan_trigger_registers_proposals():
    """POST /plan runs the Planner in the background and registers its proposals."""
    client = unlocked_client()
    plan_result = {"date": "2026-07-09", "cost_usd": 0.02, "proposals": [
        {"block": {"title": "Morning run", "start": "07:00"},
         "brief": "b", "playlist": {"name": "Run Fuel", "tracks": []}, "response": "r"}]}

    with recording_notifier() as notifier, patched(
        (planning, "budget_left", lambda: 1.0),
        (planning, "plan_tomorrow", lambda: plan_result),
    ):
        try:
            assert client.post("/api/agent/plan").status_code == 202
            deadline = time.time() + 3
            while time.time() < deadline and planning._busy["on"]:
                time.sleep(0.02)

            assert len(notifier.proposals) == 1  # pushed to the channel (bonus path)
            assert any(v["name"] == "Run Fuel" for v in proposals.PENDING.values())

            # in-app path: proposals exposed via /plan/proposals with their ids
            pj = client.get("/api/agent/plan/proposals").get_json()
            assert pj["running"] is False and len(pj["proposals"]) == 1
            p0 = pj["proposals"][0]
            assert p0["playlist"]["name"] == "Run Fuel" and p0["block"]["title"] == "Morning run"
            assert p0["proposal_id"] in proposals.PENDING  # approvable in-app
            assert p0["proposal_id"] in planning.CARD_REFS  # card kept for updates
        finally:
            proposals.clear()
            planning.CARD_REFS.clear()


def test_telegram_plan_command():
    """/plan from the owner triggers the Planner; from anyone else it's ignored."""
    client = server.app.test_client()
    os.environ["TELEGRAM_WEBHOOK_SECRET"] = "s3cr3t"
    os.environ["TELEGRAM_CHAT_ID"] = "42"
    os.environ.pop("TELEGRAM_BOT_TOKEN", None)  # telegram send is a no-op
    calls = []

    with patched((planning, "start", lambda: (calls.append(1), (True, ""))[1])):
        try:
            hdr = {"X-Telegram-Bot-Api-Secret-Token": "s3cr3t"}
            r = client.post("/api/agent/telegram/webhook",
                            json={"message": {"chat": {"id": 42}, "text": "/plan"}}, headers=hdr)
            assert r.status_code == 200 and len(calls) == 1
            # non-owner /plan -> ignored, planner NOT started
            r2 = client.post("/api/agent/telegram/webhook",
                             json={"message": {"chat": {"id": 999}, "text": "/plan"}}, headers=hdr)
            assert r2.get_json().get("type") == "ignored" and len(calls) == 1
        finally:
            os.environ.pop("TELEGRAM_WEBHOOK_SECRET", None)
            os.environ.pop("TELEGRAM_CHAT_ID", None)


if __name__ == "__main__":
    test_router_classifies_and_falls_back()
    test_router_followup_context()
    test_push_playlist_private_with_ids()
    test_push_playlist_description_respects_spotify_limit()
    test_endpoint_flow_propose_approve_reject()
    test_observatory_endpoints()
    test_commands_dictionary_and_help()
    test_spend_chat_command_and_route()
    test_unknown_run_uses_the_error_envelope()
    test_evaluator_trigger_endpoint()
    test_telegram_webhook_secret_and_actions()
    test_plan_trigger_registers_proposals()
    test_telegram_plan_command()
    print("OK: all chat tests passed")
