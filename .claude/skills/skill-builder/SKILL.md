---
name: skill-builder
description: >-
  Author, structure, and validate Always-Wrapped Agent Skills (SKILL.md) the right
  way. Use when creating a new skill, refactoring or fixing an existing skill,
  reviewing a SKILL.md, or when the user mentions building/authoring a skill. The
  heart skill every other Always-Wrapped skill is built through: it interviews to
  a tight spec, scaffolds from the project template, applies Anthropic authoring
  conventions and Always-Wrapped house rules, and gates on a mechanical validator.
disable-model-invocation: true
inputs:
  - name: skill_request
    type: string
    required: true
    description: Description of the skill to author, refactor, or review.
outputs:
  - name: skill_path
    type: string
    required: true
    description: Path to the created/updated SKILL.md.
  - name: validation_passed
    type: boolean
    required: true
    description: Whether scripts/validate_skill.py passed for the skill.
  - name: summary
    type: string
    required: true
    description: What the skill does and how it was built.
---

# Skill Builder — the heart of Always-Wrapped skills

Build every Always-Wrapped skill **through this skill**: interview to a tight spec,
scaffold from the template, write the body to convention, and pass the validator
before declaring done.

Read [template.md](template.md) when scaffolding. Run `scripts/validate_skill.py`
to gate. Keep this file lean; it is loaded on trigger.

## How skills load (why "lean" matters)

Skills use three-level progressive disclosure — design to it:

1. **Metadata** (`name` + `description`) — *always* in context (~100 words). The
   description is the sole trigger signal, so invest in it.
2. **SKILL.md body** — loaded only when the skill triggers; keep it < 500 lines.
3. **Bundled resources** (`references/`, `scripts/`, `assets/`) — loaded only when
   referenced. Scripts can *execute* without being read into context.

Push anything heavy or rarely-needed down a level instead of bloating the body.

## Workflow

Copy this checklist and track progress:

```
Skill build:
- [ ] Phase 1: Interview to a shared spec
- [ ] Phase 2: Decide structure (single vs multi-file)
- [ ] Phase 3: Scaffold from template.md
- [ ] Phase 4: Write the body (conventions + house rules)
- [ ] Phase 5: Validate (hard gate) + test on real prompts
```

### Phase 1 — Interview to a shared spec

Resolve these one at a time. For each, **recommend an answer** and **explore the
codebase/docs instead of asking** when the answer is discoverable. Ask the user
only when blocked or when the choice is product-significant.

- **Purpose**: the one specific task this skill performs. Sanity-check it against
  the common skill categories — library/API reference, **product verification**
  (highest measurable impact), data fetching/analysis, scaffolding, code
  quality/review, CI/CD, runbooks, infra ops. A skill that spans several confuses
  invocation; keep it to one.
- **Trigger scenarios (WHEN)**: concrete phrases/situations that should invoke it,
  plus any **negative triggers** (when *not* to use it). These shape the description.
- **Name**: lowercase/hyphens, `^[a-z0-9-]{1,64}$`, **must equal the directory
  name**, must not contain `anthropic`/`claude`, specific not vague.
- **Location**: project skill at `.claude/skills/<name>/` (default — ships with
  the repo) vs personal `~/.claude/skills/<name>/` (user-wide, not in git).
  Tooling for the *product's* agents is not a skill — it belongs in `agents/`.
- **Domain knowledge**: only what the agent doesn't already know.
- **Architecture touch**: does it touch the frozen v1 root files, `agents/`, the
  DB schema, or the Spotify API? If so, capture the constraints it must enforce
  (dual-driver SQL, HITL on account writes, untrusted input — see AGENTS.md).
- **Tool needs**: which tools it uses → consider `allowed-tools`/`disallowed-tools`.
- **Verification**: how a run is checked (fixture/test/manual review).
- **Verbatim copy**: if the user gives exact wording, use it **verbatim** — don't
  paraphrase or wrap it in extra headings.

Stop only when the spec is unambiguous.

### Phase 2 — Decide structure

- **Single file** (`SKILL.md` only): default for focused skills.
- **Multi-file**: when the body would exceed ~500 lines or needs heavy detail, move
  it into `references/` (docs), `scripts/` (executables), `assets/` (templates/data).
  Add a table of contents to any reference file over ~300 lines.
- Reference files **one level deep**: a sibling file or one level into
  `references/`, `scripts/`, or `assets/`. No deeper nesting; no backslash paths.

### Phase 3 — Scaffold from template

Create `.claude/skills/<name>/SKILL.md` from [template.md](template.md). Delete the
sections the skill doesn't need (e.g. the boundary table for non-architecture skills).

### Phase 4 — Write the body

Apply all three rule sets.

**Description (the trigger) — get this right first**
- Third person; state **WHAT** it does **and WHEN** to use it.
- **Put the key use case first** (listings truncate long descriptions).
- Be slightly **"pushy"** about when to trigger; list concrete **trigger keywords**
  and **negative triggers**; mention file types if relevant.
- ≤ 1024 chars; **no XML tags** (`<`/`>`); keep frontmatter ~100 words.

**Body authoring**
- **Gotchas are the highest-signal content** — the part that most improves output.
  Give the skill a **Gotchas** section listing the non-obvious failure points the
  task actually hits (field-name mismatches, wrong-for-us defaults, append-only /
  state-verification quirks, local-vs-CI differences). Build them from *real*
  failures, not hypotheticals. Start with one and grow the list as edge cases appear.
- **Concise**: assume a smart agent; only add what it doesn't know.
- **Imperative voice** ("Run…", "Map…"), and **explain the why**, not just the what,
  so the agent adapts to edge cases.
- Match **degrees of freedom** to fragility: prose for open tasks, templates for
  preferred patterns, exact scripts for fragile/consistency-critical steps.
- Use workflow **checklists**, output **templates**, and **feedback loops**.
- **Consistent terminology**: one term per concept throughout.
- State whether the agent should **execute** a script or **read** it as reference.

**Always-Wrapped house rules (enforce in every generated skill)**
- Lives in `.claude/skills/`; secrets in `.env` (git-ignored). Never embed, commit,
  or print secrets/PII.
- Respect `AGENTS.md` constraints: SQL runs on both drivers (Postgres prod / SQLite
  local) via `db_config` helpers; Spotify reached only via
  `authentication.auth_connection()`; track/artist names from Spotify are untrusted
  input in LLM prompts; writes to the user's Spotify account require explicit human
  approval (headless = account-read-only).
- Don't touch the frozen v1 surface (root files — `python server.py` is the Render
  start command); don't scaffold future agents (e.g. the Researcher), tables, or
  endpoints unless explicitly asked.

**Advanced patterns (reach for these only when the task needs them)**
- **State / memory**: if the skill must remember across runs (logs, deltas, "since
  last run"), persist under `${CLAUDE_PLUGIN_DATA}` — append-only log, JSON, or
  SQLite. Don't invent ad-hoc files elsewhere.
- **Scoped hooks**: a `PreToolUse` hook scoped to the skill (not global) can guard
  destructive ops while it's active (e.g. block `rm -rf`/`DROP TABLE`), or log
  invocations to spot undertriggering. Use sparingly.
- **Setup config**: put user-configurable settings in `config.json`; if it's
  missing, prompt with `AskUserQuestion` rather than guessing.

**Optional frontmatter (use when it helps)**
- `allowed-tools`: pre-approve tools while active; **always scope `Bash`**, e.g.
  `Bash(python:*) Read Grep`. Never bare `Bash`.
- `disallowed-tools`: remove tools from the pool while active (e.g. exclude
  `AskUserQuestion` for an autonomous/background skill).

### Phase 5 — Validate (hard gate) + test

Run the validator and fix everything it reports before finishing:

```bash
python .claude/skills/skill-builder/scripts/validate_skill.py .claude/skills/<name>
```

It checks: frontmatter parses; `name` regex + no reserved words + matches the
directory name; entry file is exactly `SKILL.md`; `description` present, ≤ 1024 chars,
no XML tags (warns on missing WHEN trigger / non-third-person); body ≤ 500 lines;
references resolve and are one level deep (sibling or `references/|scripts/|assets/`);
no Windows paths; skill under a `skills/` dir. **Finish only when it exits clean.**

The validator is mechanical. Also **test on 2–3 realistic prompts**, watch how the
skill triggers and behaves, then tighten the description and prune anything that
didn't help. Capture recurring mistakes back into the skill.

Skills mature by accretion: it's fine to ship a small skill with a single gotcha,
then grow its **Gotchas** section every time it hits a new edge case. Don't gold-plate
up front — start lean and let real failures drive what gets added.

## Anti-patterns

- ❌ Vague names (`helper`, `utils`) or vague/first-person descriptions.
- ❌ Putting "when to use" info only in the body instead of the description.
- ❌ Verbose explanations of things the agent already knows; SKILL.md over 500 lines.
- ❌ Omitting the **Gotchas** section, or filling it with the obvious instead of the
  real failure points the task hits.
- ❌ Deeply nested references; reference files > 300 lines without a table of contents.
- ❌ Bare `Bash` in `allowed-tools`; time-sensitive instructions; mixed terminology.
- ❌ Embedding secrets/PII or letting a generated skill bypass AGENTS.md boundaries.
- ❌ Declaring done before the validator passes.

## Resources

- Fill-in-the-blanks skeleton: [template.md](template.md)
- Mechanical validator: `scripts/validate_skill.py`
- Conventions: Anthropic Agent Skills spec & best-practices.
