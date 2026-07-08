# Always-Wrapped v2 — Evidence

Demonstrated evidence for the agentic v2 layer (DJ, Evaluator, Analyst, Planner,
Wrapped, Telegram timers). Evidence tiers: **demonstrated** (runnable / recorded /
reproducible) > present (code) > asserted (prose).

## Contents

| Item | What it demonstrates | Tier |
|---|---|---|
| [live app](https://always-wrapped.onrender.com) | End-to-end walkthrough of the live app / agents | demonstrated |
| `test-output.txt` | Full test suite green (11/11) at a named commit | demonstrated |
| `run-summary.md` | Table over **108 real agent runs** — steps, tools, cost, status | demonstrated |
| `runs/*.json` | 10 most-iterative run trajectories (12–16 steps each), full plan→act→observe loops with live LLM + tool calls | demonstrated |
| `hitl/pushes.jsonl` | Playlists actually pushed to Spotify **after human Approve** | demonstrated |
| `hitl/rejections.jsonl` | Proposals rejected + reasons — the Evaluator's learning input | demonstrated |

## How to reproduce

```bash
# tests (offline, deterministic)
./venv/bin/python tests/test_ingest.py   # or any tests/test_*.py

# a real agent run (needs .env with OPENAI_API_KEY + Spotify creds)
./venv/bin/python scripts/agent_smoke.py
```

Each `runs/*.json` is a harness trajectory: `metadata` (step/tool counts, token
usage, cost, terminal status) + `trajectory` (every step's messages and tool
calls). Track/artist names in tool results are untrusted input, fenced as data.

## Notes

- The complete set of 108 run logs is in the gitignored `agent-runs/` dir; the
  10 here are the most iterative, chosen from `run-summary.md`.
- Account writes (playlist push) are HITL-gated; the scheduled/headless paths are
  read-only on the Spotify account. See `hitl/` for the approve/reject record.
- The live app at https://always-wrapped.onrender.com is the demo surface.
