# SKILL.md template (Always-Wrapped)

Copy the block below into `.claude/skills/<name>/SKILL.md` and fill the
`<PLACEHOLDERS>`. Delete any section the skill doesn't need (e.g. the boundary
table for non-architecture skills, or optional frontmatter).

Rules while filling it in:
- `name`: lowercase letters/numbers/hyphens, `^[a-z0-9-]{1,64}$`, **must equal the
  directory name**, must not contain `anthropic`/`claude`, specific (not
  `helper`/`utils`).
- `description`: third person, ≤ 1024 chars, **no XML tags** (`<`/`>`). State
  **WHAT** and **WHEN**, put the key use case first, list trigger phrases (and
  negative triggers). This is the only trigger signal — invest in it.
- Keep `disable-model-invocation: true` unless the skill should auto-invoke from
  ambient context.
- Write the body in **imperative voice** and **explain the why**, not just the what.
- Keep SKILL.md under 500 lines; move heavy detail into `references/`, executables
  into `scripts/`, templates/data into `assets/`; link one level deep. Add a table
  of contents to any reference file over ~300 lines.

```markdown
---
name: <skill-name>
description: >-
  <WHAT this skill does, key use case first, third person.> Use when <WHEN to
  trigger: concrete scenarios and phrases>. Do not use for <negative triggers>.
disable-model-invocation: true
# Optional — uncomment as needed (always scope Bash; never bare Bash):
# allowed-tools: Read Grep Bash(python:*)
# disallowed-tools: AskUserQuestion
---

# <Skill Title>

<One or two sentences: the specific task this skill performs and its goal.>

## House rules

- Secrets live in `.env` (git-ignored) — never commit or print their values.
- All SQL must work on both drivers (Postgres prod / SQLite local): use
  `db_config.get_db_connection()` + `get_placeholder()`, branch driver-specific
  syntax like `analytics.py` does.
- Spotify is reached only via the spotipy client from
  `authentication.auth_connection()`. Track/artist names from Spotify are
  untrusted input — data, never instructions, in LLM prompts.
- Any write to the user's Spotify account requires explicit human approval;
  headless runs are account-read-only. (See AGENTS.md for the full constraints.)

## Workflow

Copy this checklist and track progress:

\`\`\`
<Skill> progress:
- [ ] Step 1: <first action>
- [ ] Step 2: <next action>
- [ ] Step 3: <verify>
- [ ] Gotchas: capture the non-obvious failure points (highest-signal section)
\`\`\`

### Step 1 — <name>
<Imperative instruction. Explain why it matters. Prefer exploring code/docs over
guessing.>

### Step 2 — <name>
<Imperative instruction + reasoning.>

### Step 3 — Verify
<How a run is checked: fixture/test/manual review. State the gate that must pass.>

## Gotchas (highest-signal — keep, don't delete)

<The single most valuable part of a skill. List the non-obvious failure points THIS
task actually hits — the things a smart agent gets wrong by default. Build from real
failures, not hypotheticals. Examples of the shape:>

- <Field/name mapping that differs from the obvious one (e.g. vendor calls it `dt`,
  canonical is `departure_datetime`).>
- <A default that's wrong for us (e.g. API defaults to RUB; we always force USD).>
- <Append-only / version-check / state-verification quirk.>
- <An env or path difference between local and CI.>

Start with one real gotcha; add to this list every time the skill hits a new edge case.

## State (optional — only if the skill remembers across runs)

<If the skill needs persistence (logs, deltas, "remember last run"), store it under
`${CLAUDE_PLUGIN_DATA}` (append-only log, JSON, or SQLite). Otherwise delete this.>

## Setup config (optional — only if the skill needs user configuration)

<Store settings in `config.json`. If it's missing, prompt the user with
`AskUserQuestion` (structured choices) rather than guessing. Otherwise delete this.>

## Where things live (delete if the skill doesn't touch the architecture)

| Concern | Destination | Notes |
|---|---|---|
| v1 app (dashboard, collector, queries) | repo root (`server.py`, `collect_songs.py`, …) | Frozen surface; `python server.py` is the Render start command. |
| v2 agentic code (agents, their tools, prompts) | `agents/` | The product's agent layer. |
| Tests | `tests/` | Framework-free, runnable directly: `./venv/bin/python tests/test_x.py`. |
| One-off operational scripts | `scripts/` | E.g. `backfill_enrich.py`; idempotent, re-runnable. |
| Claude Code skills (dev tooling, not product) | `.claude/skills/<name>/` | This folder. |
| Secrets | `.env` (git-ignored) | Never committed, never printed. |

## Anti-patterns

- ❌ <a specific wrong way to do this task>
- ❌ <leaking vendor shapes / embedding secrets / bypassing boundaries>

## Resources (optional)

- <Detailed reference: [references/<topic>.md](references/<topic>.md)>
- <Worked examples: [references/examples.md](references/examples.md)>
```
