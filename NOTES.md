# Key notes (terse, top-priority only)

- v1 frozen at tag `v1.0.0`; all v2 on `feat/agentic` → will merge as `v2.0.0`.
- Spotify audio-features/recommendations APIs are DEAD (Nov 2024). "Energy" is derived
  from the user's own behavior (what he plays when, skips) — this is also the moat.
- Data enriched: 4.3k plays, 100% artist_id + duration_ms, 67% non-empty genres
  (Spotify's ceiling). `duration_ms` → skip inference: gap < duration = skipped.
- Genre semantics: NULL = never fetched, '' = artist has no genres.
- Architecture (final): DJ agent (playlist loop, HITL push) + Evaluator (headless,
  soft-bias weights + decay + 15-20% exploration quota) + Researcher ONLY if real
  open-web discovery (injection boundary). No orchestrator. Wrapped report = pipeline.
- Agent loop = WS1 fellowship harness, hardened: headless, tools injected,
  max_steps + max_cost_usd caps, JSON run log per run (`agent-runs/`). Fellowship §9 story.
- LLM provider swappable via env only (`LLM_PROVIDER`/`LLM_MODEL`), agents/llm.py seam.
  OpenAI adapter tested; Anthropic adapter present, unverified (no key yet).
- DB tool = agent-written SQL behind 3 fences: SELECT-only guard, read-only
  connection, 200-row cap. SQL errors return to the model → it self-corrects.
- Track/artist names = untrusted input; fence as data in prompts, never instructions.
- HITL = Approve/Reject in chat UI; nothing writes to Spotify without the click.
  TODO: daily cost ledger at the Flask layer (per-run caps exist).
- Multi-user: NOT built (zero rubric points); §8 prose only.
- First live run 2026-07-07: agent self-corrected through 5 SQL dialect failures
  (SQLite→Postgres), then answered. One-line dialect hint in SCHEMA_DOC cut a
  comparable run 7→2 steps, $0.030→$0.005. Both run logs kept in agent-runs/.
- DJ built: propose (LLM) → verify (CODE against DB: real durations, artist cap,
  hallucinated ids) → repair rounds with ground-truth feedback → fail-closed withhold.
  Live: caught the model claiming 45min/delivering 35min + 3-same-artist; converged
  after 1 repair round once feedback included real numbers. LLMs don't do arithmetic.

## Backlog (do not forget)
- Language/Israeli playlists: artist_genres LIKE '%israeli%' + Hebrew-script regex
  + model knowledge — test live on DJ. MusicBrainz (free, artist country) if precision needed.
- Favicon: link tag in templates/index.html + static icon — bundle with chat UI work.
- Background agent = Evaluator (scheduled, headless, account-read-only): the WS4
  autonomy evidence. Runs after playlists; skip-inference -> soft bias for DJ.
- Discovery works: artist-search (genre filters ONLY work on artist search) ->
  artist_top_tracks -> confirm 0 plays in history. Israeli/Hebrew playlist live-proven.
  Verifier ground-truth extended: unknown ids resolved via Spotify tracks endpoint.
- Chat backend: budget gate -> router (off_topic never reaches an agent = hard
  scope guarantee) -> DJ persona | Analyst persona (same engine, different prompt).
  HITL: /api/agent/approve is the ONLY account-write path; push token is separate
  (.cache-push, playlist-modify-private) — collector token stays read-only forever.
  Daily cost ledger sums run logs; per-run caps + daily cap now both exist.
- Ponytail audit applied: -14 deps (redis unused; black/pylint/isort+transitives
  were deploying to prod), analytics time-filter 6x -> one helper (verified
  byte-identical vs prod data). DEFERRED to pre-merge: backfill artist images +
  delete server.py runtime fallback (~95 lines).
- BUG found+fixed: db_config read DATABASE_URL at import before load_dotenv ran ->
  every local run silently fell back to SQLite (search 'broken' locally, collector
  wrote junk local db). db_config now loads dotenv itself + reads env lazily.
- Provider roadmap: Google/Gemini support likely = OpenAIClient + base_url (OpenAI-
  compatible endpoint), not a new adapter.
- Chat UI shipped: floating widget, live step feed (polls harness trajectory),
  multi-turn sessions (provider switch = confirmed reset), proposal cards with
  Approve/Reject+reason (rejections logged as Evaluator seed data). DJ asks ONE
  clarifying question when a critical constraint is missing. Push uploads the
  brand cover (ugc-image-upload scope on the push token only).
- Evaluator shipped: headless, account-read-only; model PROPOSES bias deltas,
  CODE applies (decay 0.9/run, clamp ±0.3, full strength only at sample_n>=3).
  First live run: LEAD() skip-inference SQL, 2 biases learned for $0.057. DJ
  prompt now carries top biases + mandatory 15-20% exploration quota.
  Pushes logged to agent-runs/pushes.jsonl (Evaluator input). Pre-release evals:
  scripts/eval_agents.py (12 router cases + optional live DJ build).
- Backlog: discovery still improvable (user note after playlist-mining win).
- album_release_date added end-to-end (ingest + backfill: 4287 rows, 100%) —
  decade/era questions now data-grounded ('top 60s song' = Jackson 5, 7 plays).
  Limits doubled again: daily $20, DJ $2/run, analyst $1/run.
- Wrapped shipped (commit 9): pipelines/wrapped.py (deterministic — NOT an agent),
  11 story cards incl. DJ&Evaluator corner + era mix + listening clock; curated
  skeletons + LLM palette/copy (text color computed from luminance); editions
  cached in wrapped_editions; entry: nav button (week/month) + chat NLP route
  wrapped_request ('fresh look' regenerates); phone-frame modal, auto-advance.
  Audit fixes folded: pass-through wrapper deleted, analytics dead code, dotenv dupe.
- v2.1 (post-merge, first change): swap llm.py internals to LiteLLM — keeps
  complete() interface + FakeLLM tests; deletes adapters + PRICING (their
  maintained pricing tables fix $0-cost on non-OpenAI models); validate with
  scripts/eval_agents.py. Decision: hand-rolled seam ships v2.0.0 (demo risk +
  judgment story); LiteLLM wins long-run maintenance (model/pricing churn).
- LiteLLM+Pydantic migration (eval-gated): llm.py adapters+PRICING -> LiteLLM
  (one file; retries num_retries=2; response_format json on tool calls; litellm
  maintained pricing = accurate cost for all models). agents/schemas.py = typed
  contracts at every LLM boundary (PlaylistProposal, BiasDelta, WrappedStyle).
  Gate: 8 suites + router 12/12 + live analyst/DJ(verifier PASS)/wrapped probes.
  The seam made the swap zero-change for every agent — the abstraction proven.
- Observatory /agents: live agent graph (nodes, active pulse, tool edges, event
  feed incl. per-tool calls via harness.event_hook, cost ticker). Demo centerpiece.
- v3 backlog: in-app playback = Web Playback SDK + streaming scope + Premium (no
  data/backfill needed — capability, not data).
- DEMO_MODE=1 (public deploy): server-side 403 on all agent POSTs, wrapped serves
  cache only (never generates), chat shows curated real-output transcript with
  locked input, observatory read-only public, sync stays live. Verified live on
  a parallel 5051 instance before shipping. Owner full access = env unset (localhost).

## Access strategy (decided for submission)
- Considered: DEMO_MODE hard-lock; per-request access-code gate (X-AW-Token);
  Spotify-OAuth allowlist. All removed.
- Chosen: give the judge a REAL private link (in the proposal, NOT the public
  README). Safe because spend is bounded server-side: single-flight (one agent
  run at a time), per-run cost caps, daily budget ledger (hard refusal past
  $20/day via LiteLLM cost tables), 60s /refresh cooldown. Worst case = the
  daily cap regardless of traffic. README carries NO live link (avoids public
  discovery/spam); link shared privately with the judge only.

## Planner agent (feat/calendar-dj)
- Third agent: headless, calendar-triggered. tomorrow_blocks() reads a secret
  .ics feed (no OAuth), expands recurrences (recurring_ical_events), drops
  meetings. One LLM reasoning call per day decides — per non-meeting block —
  whether music fits and writes a one-line brief (the agentic judgment); each
  brief is delegated to the DJ (agent-as-tool, full build+verify loop).
- HITL over Telegram: send_proposal posts inline Approve/Reject buttons. The
  callback hits /api/agent/telegram/webhook — a WRITE TRIGGER, so it validates
  X-Telegram-Bot-Api-Secret-Token (hmac.compare_digest) on every call before
  touching the account; approve routes through the same _push_pending() as the
  in-app /approve (one write door), reject discards + logs negative signal.
- Calendar titles are UNTRUSTED input — fenced as data in the planner prompt,
  never instructions (same posture as track/artist names).
- Entry points: /api/agent/plan (background, single-flight, budget-gated) +
  the "plan my day" button on the observatory (new Planner + calendar nodes).
  scripts/plan_tomorrow.py = cron trigger (POSTs the endpoint so proposals live
  in the web process that handles the tap); scripts/setup_telegram.py = one-time
  setWebhook. Disabled until CALENDAR_ICS_URL + Telegram env vars are set.
- Considered-and-rejected: (a) Google Calendar OAuth — heavier, needs consent
  screen; .ics secret link is read-only + zero-auth. (b) in-app approval only —
  Telegram means approve from your phone, away from the dashboard, which is the
  actual use case (music for tomorrow, decided tonight). (c) planning in the
  cron process — proposals would be unreachable by the webhook's in-memory store.
- Packer shipped: model curates a scored candidate pool; _pack() (code) selects
  under all constraints. Supply rounds MERGE incrementally (model shirked
  re-transcribing 30 ids — measured); last-resort reserve top-up from own
  history (fit=0.3, never for mostly_never). Verifier demoted to invariant
  alarm. GATE PASSED live: the exact failed 2h Hebrew request -> 33 tracks,
  122.9/120 min, 0 violations, $0.22. Duration failures now impossible by
  construction when supply exists.
- Post-competition repo hygiene: prune agent-runs/ to 2-3 showcase logs (or move
  full set to submission folder), gitignore agent-runs/+pushes/rejections jsonl
  going forward, compute SCHEMA_DOC stats dynamically (hardcoded 4.3k/Feb-2026).
  Learned bias weights already live in the DB only — clones start fresh.
