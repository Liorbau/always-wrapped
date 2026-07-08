"""Agent harness: the plan->act->observe loop every v2 agent runs on.

Adapted from the owner's fellowship Workshop 1 harness (harness_loop.py).
Upgrades over the workshop version:
  - provider-agnostic: talks to agents.llm's normalized client, not openai
  - headless: no input() mid-loop; caller owns any human interaction
  - tools injected per agent (schemas + registry) instead of a global import
  - caps: max_steps AND optional max_cost_usd budget stop
  - run logs persisted to JSON (trajectory + metadata) for every run
  - token accounting from API-reported usage (accurate, provider-neutral)
"""

import json
import os
import re
import time

from agents.llm import get_client, cost_usd
from logging_config import configure_logger

logger = configure_logger(__name__)

DEFAULT_SYSTEM_PROMPT = """You are a helpful AI agent working to satisfy a user's request.
You have access to tools — use them when needed.

When giving a final response (not a tool call), respond with valid JSON:
{
  "thought": "your internal reasoning about what to do next",
  "response": "your message to the user",
  "satisfied": true or false
}

Set "satisfied" to true only when you have fully addressed the user's request.
"""

COMPACT_AT = 20_000  # compact when the last request's input tokens exceed this
COMPACT_WORDS = 150


def _parse_final(content):
    """Parse the model's final answer, tolerating markdown fences and prose.

    Models routinely wrap the answer JSON in ```json fences with commentary
    around it (observed live: burned 5 steps / $0.35 before this existed).
    Order: raw JSON -> fenced JSON block -> last brace-balanced object.
    """
    content = content or ""
    candidates = [content.strip()]
    candidates += re.findall(r"```(?:json)?\s*(\{.*?\})\s*```", content, re.DOTALL)
    last_obj = _last_braced_object(content)
    if last_obj:
        candidates.append(last_obj)
    for cand in candidates:
        try:
            parsed = json.loads(cand)
            if isinstance(parsed, dict) and "satisfied" in parsed:
                return parsed
        except (json.JSONDecodeError, TypeError):
            continue
    return {"thought": "", "response": content, "satisfied": False}


def _last_braced_object(text):
    """Return the last brace-balanced {...} substring, or None."""
    end = text.rfind("}")
    if end == -1:
        return None
    depth = 0
    for i in range(end, -1, -1):
        if text[i] == "}":
            depth += 1
        elif text[i] == "{":
            depth -= 1
            if depth == 0:
                return text[i : end + 1]
    return None


class AgentHarness:
    def __init__(
        self,
        llm=None,
        tool_schemas=None,
        tool_registry=None,
        system_prompt=DEFAULT_SYSTEM_PROMPT,
        max_cost_usd=None,
        run_dir="agent-runs",
    ):
        self.llm = llm or get_client()
        self.tool_schemas = tool_schemas or []
        self.tool_registry = tool_registry or {}
        self.system_prompt = system_prompt
        self.max_cost_usd = max_cost_usd
        self.run_dir = run_dir

        self.event_hook = None  # optional callable(text) — live observability
        self._log_path = None   # one persisted log per harness (avoids double-count)
        self.messages = []
        self.trajectory = []
        self.last_parsed = None  # full parsed final-answer object (incl. extra keys)
        self.cancelled = False   # set by the owner to abort between steps
        self.metadata = {
            "step_count": 0,
            "tool_call_count": 0,
            "tool_call_counts": {},
            "compaction_count": 0,
            "context_tokens_current": 0,
            "total_prompt_tokens": 0,
            "total_completion_tokens": 0,
            "cost_usd": 0.0,
            "status": "running",
        }

    # -- accounting ----------------------------------------------------------

    def _track_usage(self, usage):
        self.metadata["total_prompt_tokens"] += usage["input"]
        self.metadata["total_completion_tokens"] += usage["output"]
        self.metadata["context_tokens_current"] = usage["input"]
        self.metadata["cost_usd"] = cost_usd(
            getattr(self.llm, "model", ""),
            self.metadata["total_prompt_tokens"],
            self.metadata["total_completion_tokens"],
        )

    def _over_budget(self):
        return self.max_cost_usd is not None and self.metadata["cost_usd"] >= self.max_cost_usd

    # -- compaction ----------------------------------------------------------

    def _compact(self):
        before = self.metadata["context_tokens_current"]
        history = "\n".join(
            f"{m['role'].upper()}: {m.get('content') or ''}" for m in self.messages
        )
        resp = self.llm.complete(
            system="You compress agent conversation history.",
            messages=[
                {
                    "role": "user",
                    "content": (
                        f"Summarize the conversation below in {COMPACT_WORDS} words or fewer. "
                        "Keep all key facts, decisions, and results.\n\n" + history
                    ),
                }
            ],
        )
        self._track_usage(resp["usage"])
        summary = (resp["content"] or "").strip()
        self.messages = [
            {"role": "user", "content": f"[Compacted context — summary of prior conversation]: {summary}"}
        ]
        self.metadata["compaction_count"] += 1
        self.trajectory.append(
            {
                "type": "compaction",
                "step": self.metadata["step_count"],
                "tokens_before": before,
                "summary": summary,
            }
        )
        logger.info("Compaction #%d at ~%d tokens", self.metadata["compaction_count"], before)

    # -- main loop -----------------------------------------------------------

    def run(self, user_request, max_steps=10):
        """Run the loop until satisfied, max_steps, or cost budget. Returns final text.

        Callable again on the same instance to continue the conversation
        (e.g. feeding back verifier violations); max_steps is per call.
        """
        self.messages.append({"role": "user", "content": user_request})
        self.cancelled = False  # a Stop only aborts the run it was issued for
        self.metadata["status"] = "running"
        start_step = self.metadata["step_count"]
        satisfied = False
        final_response = ""

        while (not satisfied and not self.cancelled
               and self.metadata["step_count"] - start_step < max_steps):
            if self._over_budget():
                self.metadata["status"] = "cost_budget_reached"
                logger.warning("Cost budget $%.4f reached — stopping.", self.max_cost_usd)
                break
            if self.metadata["context_tokens_current"] >= COMPACT_AT:
                self._compact()

            self.metadata["step_count"] += 1
            step = self.metadata["step_count"]

            resp = self.llm.complete(
                system=self.system_prompt,
                messages=self.messages,
                tools=self.tool_schemas,
            )
            self._track_usage(resp["usage"])

            if resp["tool_calls"]:
                self.messages.append(
                    {"role": "assistant", "content": resp["content"], "tool_calls": resp["tool_calls"]}
                )
                for tc in resp["tool_calls"]:
                    if self.event_hook:
                        try:
                            self.event_hook(f"tool: {tc['name']}")
                        except Exception:
                            pass
                    result = self._execute_tool(tc["name"], tc["arguments"])
                    self.metadata["tool_call_count"] += 1
                    counts = self.metadata["tool_call_counts"]
                    counts[tc["name"]] = counts.get(tc["name"], 0) + 1
                    logger.info("step %d tool %s(%s)", step, tc["name"], tc["arguments"])
                    self.trajectory.append(
                        {
                            "type": "tool_call",
                            "step": step,
                            "tool": tc["name"],
                            "args": tc["arguments"],
                            "result": result,
                            "meta": dict(self.metadata),
                        }
                    )
                    self.messages.append(
                        {"role": "tool", "tool_call_id": tc["id"], "content": result}
                    )
            else:
                parsed = _parse_final(resp["content"])
                self.last_parsed = parsed
                satisfied = bool(parsed.get("satisfied", False))
                final_response = parsed.get("response", "")
                self.trajectory.append(
                    {
                        "type": "response",
                        "step": step,
                        "thought": parsed.get("thought", ""),
                        "response": final_response,
                        "satisfied": satisfied,
                        "meta": dict(self.metadata),
                    }
                )
                self.messages.append({"role": "assistant", "content": final_response})
                logger.info("step %d response (satisfied=%s)", step, satisfied)
                if not satisfied:
                    # ponytail: headless — a non-satisfied answer just loops with a nudge;
                    # interactive follow-up belongs to the caller, not the harness.
                    self.messages.append(
                        {
                            "role": "user",
                            "content": (
                                "Act now: either call a tool to make concrete progress, "
                                "or — if you already have enough data — output the final "
                                "JSON answer with satisfied=true. Do not restate analysis."
                            ),
                        }
                    )

        if self.cancelled:
            self.metadata["status"] = "cancelled"
        elif satisfied:
            self.metadata["status"] = "satisfied"
        elif self.metadata["status"] == "running":
            self.metadata["status"] = "max_steps_reached"
        self.save_run_log()
        return final_response

    def _execute_tool(self, name, args):
        fn = self.tool_registry.get(name)
        if fn is None:
            return json.dumps({"error": f"Unknown tool: {name}"})
        try:
            return fn(args)
        except Exception as exc:  # tool bugs must not kill the loop
            logger.error("Tool %s failed: %s", name, exc)
            return json.dumps({"error": f"{type(exc).__name__}: {exc}"})

    # -- run log -------------------------------------------------------------

    def save_run_log(self):
        """Persist trajectory + metadata as a timestamped JSON evidence file."""
        os.makedirs(self.run_dir, exist_ok=True)
        if self._log_path is None:
            self._log_path = os.path.join(
                self.run_dir, time.strftime("run-%Y%m%d-%H%M%S-") + os.urandom(3).hex() + ".json")
        path = self._log_path
        with open(path, "w") as f:
            json.dump(
                {"metadata": self.metadata, "trajectory": self.trajectory}, f, indent=2
            )
        logger.info("Run log saved: %s (status=%s, cost=$%.4f)",
                    path, self.metadata["status"], self.metadata["cost_usd"])
        return path
