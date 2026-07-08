<!-- captain:begin AI engineering policy (managed - do not edit inside) -->
# Engineering Ownership Protocol

This repository uses AI coding agents, but the human engineer owns the system design, tradeoffs, and final decisions.

## Before implementation

Before writing code:
- Restate the task in your own words.
- Identify affected files, modules, APIs, data models, or workflows.
- Identify meaningful design decisions.
- Present 2-4 options for important architecture or product decisions. (use the multiple-choice question tool, e.g. AskUserQuestion in Claude Code)
- Recommend one option, but wait for human approval before implementing high-impact decisions.
- Do not begin large implementation without an approved plan.

## During implementation

When writing code:
- Prefer small, reviewable diffs.
- Change at most 3 files or around 150 lines before pausing, unless explicitly approved.
- Implement step by step.
- Explain why each changed file is needed.
- Avoid unnecessary abstractions.

## Quality gates

For behavior changes:
- Add or update tests.
- Run relevant lint, typecheck, and tests when possible.
- If commands cannot be run, explain why.
- Call out hidden assumptions.
- Call out edge cases and failure modes.
- Call out security, privacy, performance, or migration risks when relevant.

## Human decision points

Pause and ask for human input before deciding:
- system architecture
- data model changes
- API contracts
- database migrations
- authentication or authorization behavior
- error-handling strategy
- major dependency additions
- irreversible or hard-to-migrate choices

## After implementation

After coding:
- Summarize changed files.
- Explain the final design.
- Explain how to verify behavior.
- List tests run.
- List remaining risks or TODOs.
- For non-trivial tasks, ask 1-3 questions to check that the human understands the implementation.
<!-- captain:end -->

@AGENTS.md
