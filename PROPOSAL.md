# Always-Wrapped v2 — Agentic Capstone Proposal

**A real-time Spotify listening tracker (live since Feb 2026, ~4.3k plays) with an
agentic layer that turns your own history into playlists — on request, on a
schedule, and learning from what you keep.**

- **Live app (demo):** https://always-wrapped.onrender.com
- **Evidence folder:** [`evidence/`](evidence/) — curated run trajectories, a
  summary over all 108 real runs, HITL push/reject records, and green test
  output. See [`evidence/README.md`](evidence/README.md).

---

## What it is

v1 is a 24/7 collector + dashboard: polls Spotify every 20 min, dedupes into one
`listening_history` table, enriches with duration and genres. That data is the
substrate. **v2 adds agents that act on it:**

- **DJ agent** — natural-language request → constraint-satisfaction loop over your
  history and Spotify's catalog → a playlist that actually meets the ask →
  human-approved push to your account.
- **Evaluator agent** — headless, post-playlist: infers plays/skips, writes *soft*
  bias weights (with decay + sample-size throttling) so the DJ leans toward what
  you keep, while every playlist reserves ~15–20% exploration to avoid an echo
  chamber. Read-only on the Spotify account.
- **Planner + Telegram timers** — "every Sun–Thu 07:30, a 50-min upbeat train
  playlist": a standing request fires on schedule, the DJ builds it, and it lands
  in Telegram with Approve/Reject. The account write still waits for your tap.

---

## Are the evidence runs good or bad? (honest answer)

**Good runs — real, successful playlist generations — captured during development
and hardening (July 7–8), not a scripted demo.** Across **108 recorded runs**:

- **88 `satisfied`** — the agent converged and produced a playlist meeting the
  constraints (duration, familiarity mix, mood, artist cap, never-played discovery).
- **14 `wrapped-generation`** — the deterministic Wrapped report pipeline.
- **3 `max_steps_reached`** — the per-run **safety cap firing as designed**. These
  still returned a coherent playlist; they simply used their full step budget.
  They are kept deliberately — they are evidence the caps work, not product
  failures.
- **3 `cancelled`** — runs interrupted mid-build during development.

The 10 curated trajectories in `evidence/runs/` are the most *iterative* (12–16
steps, up to 29 tool calls each) — they show the loop genuinely working, e.g. one
16-step run chaining `query_history ×11 → artist_top_tracks ×10 → search_spotify
×4 → discover_new_tracks ×3 → get_audio_features` to build a 2-hour "happy,
never-heard-before" set.

**These are development-time runs** — real requests the owner made while building
and testing. That is called out so nothing is oversold: the value is that they are
reproducible, logged, and show real iteration and self-correction, including runs
that hit the caps.

---

## Rubric mapping

### Agentic depth (25)
Real plan→act→observe loops, not one-shot prompts:
- **DJ constraint loop:** propose (LLM) → **verify in CODE against the DB** (real
  durations, artist-repeat cap, hallucinated track ids) → repair rounds with
  ground-truth feedback → fail-closed withhold if it can't satisfy. Live example
  captured: the model claimed 45 min / delivered 35 min with 3 same-artist tracks;
  it converged after one repair round *once the feedback carried real numbers*
  (LLMs can't do the arithmetic — the code does).
- **Self-correction:** first live run self-healed through 5 SQLite→Postgres SQL
  dialect errors, then answered; a one-line dialect hint in the schema doc cut a
  comparable run 7→2 steps and $0.030→$0.005 (both logs kept).
- **Agent-as-tool:** the Planner delegates each calendar block to the DJ; Spotify
  catalog search is a *tool* of the DJ, not a separate agent.
- **Learning loop:** the Evaluator closes the loop with soft, decaying biases.

### Engineering (20)
- Provider-agnostic LLM seam (`agents/llm.py`, swappable by env), Pydantic
  contracts at the boundary, a hardened harness (max_steps + max_cost caps, JSON
  run log per run).
- Dual-driver DB (SQLite local / Postgres prod) with every query branched.
- **11/11 tests green** (`evidence/test-output.txt`), framework-free and runnable.
- Thin Flask routes; behavior lives in `agents/`.

### Product (15)
Always-on tracker + on-demand DJ + scheduled Telegram playlists. Real artifact
shipped: playlist **"Favorite 90's Hits"** (60 min asked → 72.6 min delivered,
mostly-familiar) pushed to Spotify after Approve (`evidence/hitl/pushes.jsonl`).

### Moat (15)
Spotify's audio-features / recommendations / related-artists APIs are **dead**
(deprecated Nov 2024 for this tier). "Energy"/mood is derived **behaviorally from
the user's own history** — what they play at which hours, skip patterns (skip
inferred from `played_at` gaps vs `duration_ms`). That behavioral model is the
defensible core; it can't be copied from a public API.

### Safety (15)
- **HITL on every account write** — nothing reaches Spotify without an explicit
  Approve (chat button or Telegram tap). `evidence/hitl/` is the approve/reject
  record.
- **Headless = read-only** on the Spotify account (Evaluator, scheduled timers).
- **Owner-locked Telegram webhook:** secret-token validated on every call *and*
  the Approve/Reject callback verifies the tapper's chat id (fail closed).
- **Caps:** per-run max_steps + max_cost, plus a daily budget ledger at the Flask
  layer that refuses new agent work past the cap.
- **Prompt-injection boundary:** track/artist names are untrusted input, fenced as
  data in every prompt; the DB tool is SELECT-only behind a read-only connection
  with a row cap.

### Complexity (5) / Demo (5)
Multi-agent system with a learning loop, dual persistence, and a live deployment;
demo via the live URL + reproducible runs (`evidence/runs/`).

---

## How to reproduce

```bash
./venv/bin/python tests/test_ingest.py       # any tests/test_*.py — offline, deterministic
./venv/bin/python scripts/agent_smoke.py     # a real DJ run (needs .env keys)
```
Each `evidence/runs/*.json` is a full harness trajectory (metadata: step/tool
counts, tokens, cost, terminal status).

## Honest scoping / limitations
- Multi-user is **not** built (single-user by design; zero rubric points for it).
- Anthropic LLM adapter is present but unverified (no key at build time); OpenAI
  adapter is the tested path.
- Researcher/open-web discovery is deferred until real discovery is added, behind
  a prompt-injection boundary.
