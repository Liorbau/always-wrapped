"""Chat backend tests: router, ledger, HITL push, endpoint flow — all offline.

Runnable directly:  ./venv/bin/python tests/test_chat.py
"""

import json
import os
import sys
import tempfile
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from agents.ledger import daily_spent, budget_left
from agents.router import route_message
from agents.spotify_push import push_playlist
from tests.test_harness import FakeLLM

import server
import agents.api as agents_api


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


def test_ledger_sums_today_only():
    with tempfile.TemporaryDirectory() as tmp:
        day = time.strftime("%Y%m%d")
        for name, cost in ((f"run-{day}-010101.json", 0.30),
                           (f"run-{day}-020202.json", 0.20),
                           ("run-20200101-000000.json", 9.99)):
            with open(os.path.join(tmp, name), "w") as f:
                json.dump({"metadata": {"cost_usd": cost}}, f)
        assert abs(daily_spent(run_dir=tmp) - 0.50) < 1e-9
        assert budget_left(run_dir=tmp) > 0


class FakePushSpotify:
    def __init__(self):
        self.added = None

    def current_user(self):
        return {"id": "lior"}

    def user_playlist_create(self, user_id, name, public, description):
        assert public is False, "playlists must be private"
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
    assert push_playlist({"tracks": []}, sp=sp)["error"]


def _poll(client, run_id, timeout=5.0):
    deadline = time.time() + timeout
    while time.time() < deadline:
        r = client.get(f"/api/agent/run/{run_id}").get_json()
        if r.get("done"):
            return r
        time.sleep(0.02)
    raise AssertionError("run never finished")


def test_endpoint_flow_propose_approve_reject():
    import agents.dj as dj_mod
    client = server.app.test_client()
    originals = (agents_api.route_message, agents_api.get_client,
                 agents_api.push_playlist, agents_api.budget_left,
                 dj_mod.verify_playlist, agents_api.REJECTIONS_LOG)
    pushed = []
    PROPOSAL_JSON = json.dumps({
        "thought": "t", "response": "here you go", "satisfied": True,
        "playlist": {"name": "Mix", "target_duration_min": 45,
                     "tracks": [{"track_id": "t1"}]}})
    with tempfile.TemporaryDirectory() as tmp:
        agents_api.budget_left = lambda: 1.0
        agents_api.route_message = lambda m, context=None: {
            "cake": "off_topic", "mix": "playlist_request"}.get(m, "data_question")
        agents_api.get_client = lambda provider=None, model=None: FakeLLM([
            {"content": PROPOSAL_JSON}])
        agents_api.push_playlist = lambda pl: (pushed.append(pl) or
                                               {"playlist_id": "pl1", "url": "u", "track_count": 1})
        agents_api.REJECTIONS_LOG = os.path.join(tmp, "rejections.jsonl")
        original_pushes = agents_api.PUSHES_LOG
        agents_api.PUSHES_LOG = os.path.join(tmp, "pushes.jsonl")
        dj_mod.verify_playlist = lambda pl: []
        # route run logs to tmp, not the real evidence dir
        real_build_dj, real_build_analyst = agents_api.build_dj, agents_api.build_analyst
        agents_api.build_dj = lambda llm=None: real_build_dj(llm=llm, run_dir=tmp)
        agents_api.build_analyst = lambda llm=None: real_build_analyst(llm=llm, run_dir=tmp)
        try:
            # off-topic refused synchronously, no run started
            r = client.post("/api/agent/chat", json={"message": "cake"})
            assert r.get_json()["type"] == "refusal" and r.status_code == 200

            # playlist request -> 202 + run_id -> poll to proposal; nothing pushed
            r = client.post("/api/agent/chat", json={"message": "mix", "session_id": "s1"})
            assert r.status_code == 202
            body = r.get_json()
            assert body["route"] == "playlist_request" and body["session_id"] == "s1"
            done = _poll(client, body["run_id"])
            result = done["result"]
            assert result["type"] == "playlist_proposal" and not pushed
            pid = result["proposal_id"]

            # multi-turn: same session reuses the SAME dj harness object
            dj_first = agents_api.SESSIONS["s1"]["dj"]
            r2 = client.post("/api/agent/chat", json={"message": "mix", "session_id": "s1"})
            _poll(client, r2.get_json()["run_id"])
            assert agents_api.SESSIONS["s1"]["dj"] is dj_first

            # provider switch resets the session (fresh conversation)
            r3 = client.post("/api/agent/chat",
                             json={"message": "mix", "session_id": "s1", "provider": "anthropic"})
            _poll(client, r3.get_json()["run_id"])
            assert agents_api.SESSIONS["s1"]["dj"] is not dj_first

            # approve -> exactly one push, proposal consumed
            r = client.post("/api/agent/approve", json={"proposal_id": pid}).get_json()
            assert r["type"] == "pushed" and len(pushed) == 1
            assert client.post("/api/agent/approve", json={"proposal_id": pid}).status_code == 404

            # reject with reason -> logged for the Evaluator, never pushed
            pid2 = _poll(client, client.post(
                "/api/agent/chat", json={"message": "mix", "session_id": "s1"}
            ).get_json()["run_id"])["result"]["proposal_id"]
            r = client.post("/api/agent/reject",
                            json={"proposal_id": pid2, "reason": "too mellow"}).get_json()
            assert r["type"] == "rejected" and len(pushed) == 1
            logged = json.loads(open(agents_api.REJECTIONS_LOG).read().strip())
            assert logged["reason"] == "too mellow"

            # budget exhausted -> 429
            agents_api.budget_left = lambda: -0.01
            assert client.post("/api/agent/chat", json={"message": "mix"}).status_code == 429
        finally:
            (agents_api.route_message, agents_api.get_client, agents_api.push_playlist,
             agents_api.budget_left, dj_mod.verify_playlist,
             agents_api.REJECTIONS_LOG) = originals
            agents_api.build_dj, agents_api.build_analyst = real_build_dj, real_build_analyst
            agents_api.PUSHES_LOG = original_pushes
            agents_api.SESSIONS.clear()


def test_observatory_endpoints():
    client = server.app.test_client()
    assert client.get("/agents").status_code == 200
    r = client.get("/api/agent/activity").get_json()
    assert set(r) == {"active", "events", "daily_cost", "daily_budget"}
    assert r["active"] is None or "agent" in r["active"]


def test_evaluator_trigger_endpoint():
    import time as _t
    client = server.app.test_client()
    originals = (agents_api.build_evaluator, agents_api.run_evaluator, agents_api.budget_left)
    agents_api.budget_left = lambda: 1.0
    agents_api.build_evaluator = lambda: type("H", (), {"event_hook": None, "trajectory": [],
                                                        "metadata": {"cost_usd": 0}})()
    agents_api.run_evaluator = lambda harness=None: {"report": "learned stuff",
                                                     "applied": 2, "cost_usd": 0.01}
    try:
        r = client.post("/api/agent/evaluate")
        assert r.status_code == 202
        rid = r.get_json()["run_id"]
        deadline = _t.time() + 3
        while _t.time() < deadline:
            s = client.get(f"/api/agent/run/{rid}").get_json()
            if s.get("done"):
                assert s["result"]["response"] == "learned stuff"
                break
            _t.sleep(0.02)
        else:
            raise AssertionError("evaluator run never finished")
        feed = client.get("/api/agent/activity").get_json()["events"]
        assert any("learned 2 preference" in e["text"] for e in feed)
    finally:
        (agents_api.build_evaluator, agents_api.run_evaluator, agents_api.budget_left) = originals



def test_telegram_webhook_secret_and_actions():
    """The webhook is a write trigger — secret gates it; approve pushes, reject discards."""
    client = server.app.test_client()
    originals = (agents_api.push_playlist, agents_api.REJECTIONS_LOG, agents_api.PUSHES_LOG)
    pushed = []
    os.environ["TELEGRAM_WEBHOOK_SECRET"] = "s3cr3t"
    os.environ["TELEGRAM_CHAT_ID"] = "42"  # owner id for the callback owner-check
    os.environ.pop("TELEGRAM_BOT_TOKEN", None)  # telegram calls no-op (no network)
    with tempfile.TemporaryDirectory() as tmp:
        agents_api.push_playlist = lambda pl: (pushed.append(pl) or {"url": "u"})
        agents_api.REJECTIONS_LOG = os.path.join(tmp, "rej.jsonl")
        agents_api.PUSHES_LOG = os.path.join(tmp, "push.jsonl")
        try:
            def cb(pid, action, uid=42):
                return {"callback_query": {"id": "c1", "from": {"id": uid},
                                           "data": f"{action}:{pid}"}}

            # wrong secret -> 403, nothing touched
            agents_api.PENDING_PROPOSALS["p1"] = {"name": "A", "tracks": [{"track_id": "t1"}]}
            r = client.post("/api/agent/telegram/webhook", json=cb("p1", "approve"),
                            headers={"X-Telegram-Bot-Api-Secret-Token": "wrong"})
            assert r.status_code == 403 and not pushed and "p1" in agents_api.PENDING_PROPOSALS

            # right secret but a non-owner tapper -> ignored, nothing pushed
            r = client.post("/api/agent/telegram/webhook", json=cb("p1", "approve", uid=999),
                            headers={"X-Telegram-Bot-Api-Secret-Token": "s3cr3t"})
            assert r.status_code == 200 and not pushed and "p1" in agents_api.PENDING_PROPOSALS

            # right secret + approve -> pushed once, proposal consumed
            r = client.post("/api/agent/telegram/webhook", json=cb("p1", "approve"),
                            headers={"X-Telegram-Bot-Api-Secret-Token": "s3cr3t"})
            assert r.status_code == 200 and len(pushed) == 1
            assert "p1" not in agents_api.PENDING_PROPOSALS

            # right secret + reject -> discarded + logged, no extra push
            agents_api.PENDING_PROPOSALS["p2"] = {"name": "B", "tracks": []}
            r = client.post("/api/agent/telegram/webhook", json=cb("p2", "reject"),
                            headers={"X-Telegram-Bot-Api-Secret-Token": "s3cr3t"})
            assert r.status_code == 200 and len(pushed) == 1
            assert "p2" not in agents_api.PENDING_PROPOSALS
            assert json.loads(open(agents_api.REJECTIONS_LOG).read().strip())["playlist"]["name"] == "B"
        finally:
            (agents_api.push_playlist, agents_api.REJECTIONS_LOG,
             agents_api.PUSHES_LOG) = originals
            os.environ.pop("TELEGRAM_WEBHOOK_SECRET", None)
            os.environ.pop("TELEGRAM_CHAT_ID", None)
            agents_api.PENDING_PROPOSALS.clear()


def test_plan_trigger_registers_proposals():
    """POST /plan runs the Planner in the background and registers its proposals."""
    import time as _t
    client = server.app.test_client()
    originals = (agents_api.plan_tomorrow, agents_api.budget_left)
    sent = []
    agents_api.budget_left = lambda: 1.0
    agents_api.plan_tomorrow = lambda: {"date": "2026-07-09", "cost_usd": 0.02, "proposals": [
        {"block": {"title": "Morning run", "start": "07:00"},
         "brief": "b", "playlist": {"name": "Run Fuel", "tracks": []}, "response": "r"}]}
    orig_send = agents_api.telegram.send_proposal
    agents_api.telegram.send_proposal = lambda block, pl, pid, chat_id=None: (
        sent.append(pid) or {"result": {}})
    try:
        r = client.post("/api/agent/plan")
        assert r.status_code == 202
        deadline = _t.time() + 3
        while _t.time() < deadline and agents_api._planner_busy["on"]:
            _t.sleep(0.02)
        assert len(sent) == 1                       # one Telegram notification sent (bonus channel)
        assert any(v["name"] == "Run Fuel" for v in agents_api.PENDING_PROPOSALS.values())
        # in-app path: proposals queued + exposed via /plan/proposals with their ids
        pj = client.get("/api/agent/plan/proposals").get_json()
        assert pj["running"] is False and len(pj["proposals"]) == 1
        p0 = pj["proposals"][0]
        assert p0["playlist"]["name"] == "Run Fuel" and p0["block"]["title"] == "Morning run"
        assert p0["proposal_id"] in agents_api.PENDING_PROPOSALS   # approvable in-app
    finally:
        (agents_api.plan_tomorrow, agents_api.budget_left) = originals
        agents_api.telegram.send_proposal = orig_send
        agents_api.PENDING_PROPOSALS.clear()


def test_telegram_plan_command():
    """/plan from the owner triggers the Planner; from anyone else it's ignored."""
    client = server.app.test_client()
    os.environ["TELEGRAM_WEBHOOK_SECRET"] = "s3cr3t"
    os.environ["TELEGRAM_CHAT_ID"] = "42"
    os.environ.pop("TELEGRAM_BOT_TOKEN", None)  # telegram send is a no-op
    calls = []
    orig = agents_api._start_planner_run
    agents_api._start_planner_run = lambda: (calls.append(1), (True, ""))[1]
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
        agents_api._start_planner_run = orig
        os.environ.pop("TELEGRAM_WEBHOOK_SECRET", None)
        os.environ.pop("TELEGRAM_CHAT_ID", None)


if __name__ == "__main__":
    test_router_classifies_and_falls_back()
    test_router_followup_context()
    test_ledger_sums_today_only()
    test_push_playlist_private_with_ids()
    test_endpoint_flow_propose_approve_reject()
    test_observatory_endpoints()
    test_telegram_webhook_secret_and_actions()
    test_plan_trigger_registers_proposals()
    test_telegram_plan_command()
    print("OK: all chat tests passed")
