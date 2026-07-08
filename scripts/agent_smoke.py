"""Live smoke run: the agent harness + query_history tool against real data.

Reproducible evidence run — the agent writes its own SQL, observes results,
iterates, and answers. Trajectory lands in agent-runs/.

    ./venv/bin/python scripts/agent_smoke.py ["your question"]
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from agents.harness import AgentHarness
from agents.tools import TOOL_SCHEMAS, TOOL_REGISTRY

DEFAULT_QUESTION = (
    "What are this user's top 3 genres on weekday afternoons (12:00-18:00 UTC), "
    "and which artist drives each of them? Base every claim on queries."
)


def main():
    question = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_QUESTION
    harness = AgentHarness(
        tool_schemas=TOOL_SCHEMAS,
        tool_registry=TOOL_REGISTRY,
        max_cost_usd=0.25,  # hard budget for a smoke run
    )
    answer = harness.run(question, max_steps=8)

    m = harness.metadata
    print("\n=== ANSWER ===\n" + answer)
    print(
        f"\n=== RUN ===\nstatus={m['status']}  steps={m['step_count']}  "
        f"tool_calls={m['tool_call_count']}  cost=${m['cost_usd']:.4f}"
    )


if __name__ == "__main__":
    main()
