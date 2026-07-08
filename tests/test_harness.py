"""Harness loop tests — no network, no API keys: a scripted FakeLLM drives the loop.

Runnable directly:  ./venv/bin/python tests/test_harness.py
"""

import json
import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from agents.harness import AgentHarness


class FakeLLM:
    """Returns scripted responses in order; repeats the last one if exhausted."""

    model = "gpt-4o"

    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = 0

    def complete(self, system, messages, tools=None):
        self.calls += 1
        resp = self.responses.pop(0) if len(self.responses) > 1 else self.responses[0]
        return {
            "content": resp.get("content"),
            "tool_calls": resp.get("tool_calls", []),
            "usage": resp.get("usage", {"input": 100, "output": 20}),
        }


def final(text, satisfied=True):
    return {"content": json.dumps({"thought": "t", "response": text, "satisfied": satisfied})}


def tool_call(name, args):
    return {"tool_calls": [{"id": "tc1", "name": name, "arguments": args}]}


def test_loop_executes_tool_then_finishes():
    seen = []
    registry = {"echo": lambda args: json.dumps({"echoed": args["x"], "_": seen.append(args)})}
    llm = FakeLLM([tool_call("echo", {"x": 42}), final("done")])
    with tempfile.TemporaryDirectory() as tmp:
        h = AgentHarness(llm=llm, tool_registry=registry, run_dir=tmp)
        result = h.run("do the thing")
        assert result == "done"
        assert seen == [{"x": 42}]
        assert h.metadata["status"] == "satisfied"
        assert h.metadata["tool_call_counts"] == {"echo": 1}
        # tool result was observed by the model on the next turn
        assert any(m["role"] == "tool" and "42" in m["content"] for m in h.messages)
        # run log persisted with full trajectory
        run_files = os.listdir(tmp)
        assert len(run_files) == 1
        log = json.load(open(os.path.join(tmp, run_files[0])))
        assert [e["type"] for e in log["trajectory"]] == ["tool_call", "response"]


def test_max_steps_cap():
    llm = FakeLLM([final("not yet", satisfied=False)])
    with tempfile.TemporaryDirectory() as tmp:
        h = AgentHarness(llm=llm, run_dir=tmp)
        h.run("impossible task", max_steps=3)
        assert h.metadata["step_count"] == 3
        assert h.metadata["status"] == "max_steps_reached"


def test_cost_budget_cap():
    # each fake call ~100 in/20 out on gpt-4o pricing => ~$0.00045/step
    llm = FakeLLM([final("not yet", satisfied=False)])
    with tempfile.TemporaryDirectory() as tmp:
        h = AgentHarness(llm=llm, max_cost_usd=0.001, run_dir=tmp)
        h.run("expensive task", max_steps=50)
        assert h.metadata["status"] == "cost_budget_reached"
        assert h.metadata["step_count"] < 50


def test_unknown_tool_and_tool_crash_survive():
    registry = {"boom": lambda args: 1 / 0}
    llm = FakeLLM(
        [tool_call("nope", {}), tool_call("boom", {}), final("recovered")]
    )
    with tempfile.TemporaryDirectory() as tmp:
        h = AgentHarness(llm=llm, tool_registry=registry, run_dir=tmp)
        result = h.run("break stuff")
        assert result == "recovered"
        errors = [e["result"] for e in h.trajectory if e["type"] == "tool_call"]
        assert "Unknown tool" in errors[0]
        assert "ZeroDivisionError" in errors[1]


def test_non_json_final_answer_does_not_crash():
    llm = FakeLLM([{"content": "plain text, not JSON"}, final("ok")])
    with tempfile.TemporaryDirectory() as tmp:
        h = AgentHarness(llm=llm, run_dir=tmp)
        result = h.run("talk plainly")
        assert result == "ok"  # first reply treated as unsatisfied, loop continued


def test_cancellation_stops_the_loop():
    # cancel mid-run via the tool-call event hook (the real Stop path); run()
    # resets cancelled at entry so a stop only aborts the run it fired during.
    registry = {"noop": lambda args: "{}"}
    llm = FakeLLM([tool_call("noop", {}), final("done")])
    with tempfile.TemporaryDirectory() as tmp:
        h = AgentHarness(llm=llm, tool_registry=registry, run_dir=tmp)
        h.event_hook = lambda text: setattr(h, "cancelled", True)
        h.run("anything", max_steps=10)
        assert h.metadata["status"] == "cancelled"
        # a fresh run on the same harness works again (cancelled was reset)
        llm2 = FakeLLM([final("ok")])
        h.llm = llm2
        assert h.run("again", max_steps=3) == "ok"
        assert h.metadata["status"] == "satisfied"


def test_fenced_json_final_answer_is_parsed():
    """Observed live: models wrap the answer JSON in prose + ```json fences."""
    wrapped = (
        "Great news, here is the result you asked for:\n\n"
        "```json\n"
        + json.dumps({"thought": "t", "response": "fenced", "satisfied": True})
        + "\n```\n\nEnjoy!"
    )
    llm = FakeLLM([{"content": wrapped}])
    with tempfile.TemporaryDirectory() as tmp:
        h = AgentHarness(llm=llm, run_dir=tmp)
        result = h.run("wrap it")
        assert result == "fenced"
        assert h.metadata["status"] == "satisfied"


def test_prose_with_bare_trailing_json_is_parsed():
    payload = json.dumps({"thought": "t", "response": "trailing", "satisfied": True,
                          "playlist": {"tracks": []}})
    llm = FakeLLM([{"content": "Some analysis first.\n" + payload}])
    with tempfile.TemporaryDirectory() as tmp:
        h = AgentHarness(llm=llm, run_dir=tmp)
        result = h.run("no fence")
        assert result == "trailing"
        assert h.last_parsed["playlist"] == {"tracks": []}


if __name__ == "__main__":
    test_loop_executes_tool_then_finishes()
    test_max_steps_cap()
    test_cost_budget_cap()
    test_unknown_tool_and_tool_crash_survive()
    test_non_json_final_answer_does_not_crash()
    test_cancellation_stops_the_loop()
    test_fenced_json_final_answer_is_parsed()
    test_prose_with_bare_trailing_json_is_parsed()
    print("OK: all harness tests passed")
