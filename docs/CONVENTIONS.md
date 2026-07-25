# Engineering Conventions — Python Backend + Vanilla JS Frontend

Self-contained rulebook for a fullstack app that is **not** NestJS/React/TypeScript.
Copy this file into the other project and treat it as the execution source of truth
for structure, layering, and coding habits.

Stack assumptions:

- **Backend:** Python (FastAPI preferred; Flask/Django also fine if the same layers exist)
- **Frontend:** Vanilla JS (ES modules), HTML, CSS — no React/Vue/Svelte required
- **Contract:** HTTP JSON API, documented and stable (OpenAPI or equivalent)

---

## 1. Ownership and process

- The human owns system design, tradeoffs, and final decisions.
- Before large work: restate the task, list affected modules/APIs/data models, and
  present options for irreversible choices (data model, auth, public API, migrations).
- Prefer small, reviewable diffs. Pause before architecture / data-model / API /
  auth / migration decisions — do not silently choose.
- After non-trivial changes: verify with lint/typecheck/tests; call out edge cases
  and security risks.
- One logical concern per commit. Message format: `<topic>: <lowercase verb message>.`

---

## 2. Shared goals

- Build iteratively; each change is additive, not a rewrite.
- Contract-first between frontend and backend.
- Clear module boundaries; predictable errors; fail visibly.
- Type safety where the language allows (Python type hints; JS JSDoc or a thin
  shared schema — do not invent a second undocumented contract).

---

## 3. API contract

- One source of truth for request/response shapes (OpenAPI / shared schema file).
- Both sides honor the same error envelope, e.g.:

  ```json
  { "error": { "code": "VALIDATION_ERROR", "message": "...", "details": {} } }
  ```

- Status mapping (keep consistent):
  - auth failure → `401`
  - authorization / not a participant → `403` (never leak data or fake `404`)
  - validation → `400`
  - duplicate / conflict → `409`
- Derive identity from the verified token (middleware), never from the request body.
- Do not change the error envelope casually — the frontend depends on it.

---

## 4. Backend layering

Every endpoint flows:

```
Router (HTTP) → Orchestrator / Use-case (one per endpoint)
  → Service (single domain) → Repository (DB only)
```

### Roles

| Layer | Owns | Must not |
| --- | --- | --- |
| **Router / controller** | Path, status, parse body/query, call `execute(...)`, return DTO | Business logic, DB access |
| **Orchestrator** | Authorize → validate → compose services/repos (and transactions) → map response | Framework request objects leaking down; owning domain rules forever |
| **Service** | Single-domain business rules | Calling other domains' services; touching the ORM/session directly |
| **Repository** | Persistence queries/commands | HTTP, auth policy, cross-domain workflow |

Rules:

- Keep thin layers for uniformity even when an orchestrator is a short forward.
- Orchestrators **compose**; services stay inside one domain.
- Framework types (Starlette `Request`, Flask `request`, Django `HttpRequest`,
  upload file objects) stay at the edge. Convert to plain dicts / dataclasses /
  Pydantic models before services see them.
- Enforce each input constraint once at the edge; map failures to the error envelope.
- One real job per file (~150-line soft cap). Extract pure helpers next to the
  owner (`*_mappers.py`, `*_cursor.py`, chunking helpers, etc.).
- Name swappable seams by **role**, not vendor: e.g. `StorageProvider` protocol +
  `S3Storage` implementation. Services depend on the protocol.

### Suggested backend layout

```
backend/
  app/
    main.py                 # bootstrap: middleware, exception handlers, CORS
    config.py               # env validation; secrets from environment only
    common/                 # error envelope, logging helpers
    errors.py               # AppError + error codes
    modules/
      auth/
        router.py
        orchestrators/      # signup.py, login.py, ...
        service.py
        repository.py
        schemas.py          # Pydantic / dataclasses (transport DTOs)
        mappers.py          # pure doc → DTO reshapes
      users/
      conversations/
      messages/
      ...
  tests/
```

Adapt names to the framework (`api/`, `routers/`, Django apps) — keep the
**roles**, not Nest-style folder names.

### Data model habits

- Stable string ids (UUIDs) as primary keys unless the DB forces otherwise.
- **Reference** high-volume / unbounded data (own collection/table + id).
- **Denormalize** only small, read-hot scalars a list view needs (e.g. last
  message preview), and update them wherever the source changes.
- **Embed** only small, owned, always-loaded value objects.
- Repository → API boundary: mappers strip internals/secrets and reshape to the
  public DTO. Routers never return raw ORM rows.

### Auth, secrets, validation

- Protect every private route; missing/invalid token → `401`.
- Participant / ownership checks → `403` when the caller is authenticated but
  not allowed.
- Passwords: hash (bcrypt/argon2); never return or log the hash or plaintext.
- Load secrets (`JWT_SECRET`, `DATABASE_URL`, …) from env only; commit
  `.env.example`, never a real `.env`.
- Validate with Pydantic (or equivalent) before business logic; reject unknown
  fields when practical.

---

## 5. Frontend structure (vanilla JS)

Organize by **domain/screen**, not by generic widget dumps.

### Top-level layout

```
frontend/
  index.html
  src/
    main.js                 # boot: mount app, wire global listeners
    api/
      client.js             # base URL, auth header, error mapping
      types.js              # optional: shared error helpers / JSDoc typedefs
      # multi-feature actions may live here; single-feature actions live under the feature
    shared/
      constants/
      utils/                # pure helpers (values in → values out)
      dom/                  # tiny reusable DOM helpers if needed
    features/
      auth/
      conversations/
      messages/
      profile/
      ...
    styles/                 # global CSS; feature CSS co-located when local
```

### Feature anatomy

```
features/<domain>/
  api.js                    # calls for this domain (uses api/client.js)
  state.js                  # domain state + transitions (or split by action)
  view.js                   # DOM render / update for this domain's UI
  events.js                 # wire UI events → state/api (optional if small)
  constants.js
  utils.js                  # pure helpers only
  styles.css                # optional, co-located
```

Only add files a domain needs. A domain never imports another domain's
internals — share via `shared/`, `api/`, or an explicit public export from the
owning feature.

### Presentational vs “container” (without React)

Same split, different names:

| Role | Responsibility |
| --- | --- |
| **view** | Browser surface: create/update DOM, bind element events to callbacks it receives |
| **state / events (wiring)** | Fetch, auth, stale-response guards, decide what to render next |

Rules:

- Views do not know about tokens, base URLs, or repositories.
- Wiring modules do not build large HTML strings inline when a view owns that UI.
- Decompose by **concern** (a distinct control, message, sub-view), not by cloning
  near-identical leaves. Prefer one parameterized helper over many copies.
- Keep a **single source of truth** for each piece of client state.
- Guard against stale async results before writing state (ignore outdated responses
  when a newer request superseded them).
- Derive labels from API data when the server is the source of truth; do not
  hardcode parallel lookup tables that can drift.

### Soft file roles

| Suffix / name | Contents |
| --- | --- |
| `view.js` | DOM only |
| `state.js` / `events.js` | behavior, async, wiring |
| `api.js` | HTTP calls for the feature |
| `utils.js` | pure transforms |
| `constants.js` | values, labels, messages (not styles) |
| `styles.css` | presentation only |

One responsibility per file. Create only what you need.

---

## 6. Coding principles (both sides)

1. Prefer clear names (`input_value`, `user_id`) over vague ones (`data`, `tmp`).
2. Never fail validation silently — return or show a clear error.
3. Keep validation behavior consistent across similar flows.
4. Do not silently substitute fallback values that mask bugs; fail visibly.
5. Keep leaf/presentational UI decoupled from infra (HTTP, storage, secrets).
6. One consistent error shape end-to-end.
7. Use async/await consistently within a layer; do not mix callback styles in new code.
8. Log with context (method, path, status, duration, key ids) — never secrets.
9. Functions should return a meaningful value (result, id, status, DTO). A
   “returns nothing” domain function is usually a design smell — rework it.
   Framework lifecycle hooks are the exception.
10. Keep each function at a **single level of abstraction**. If a unit only
    orchestrates named helpers but then inlines one ad-hoc block, extract that
    block into a peer helper.
11. Inject or pass swappable external providers (LLM, embeddings, storage) behind
    an abstraction — services stay provider-agnostic.
12. Respect batch/size/rate limits when calling external APIs in loops.
13. Mutually exclusive outcomes get separate code paths (e.g. a refusal must not
    also carry citations meant for a success path).
14. Derive shared shapes from one source of truth (OpenAPI → generated types, or
    one schema module) instead of hand-duplicating DTOs that can drift.
15. **Missing values:** in Python prefer `is None` / `is not None`. In JS, be
    intentional: use truthiness when empty is invalid; use `== null` when `0` or
    `''` are legitimate.
16. Pure mappers/utils only reshape data. Anything that *does work* or holds a
    dependency (hashing, HTTP, clock, code generation) is an injectable/explicit
    collaborator — not a hidden static side-effect helper.
17. Default to zero comments. Names and structure explain the code. A comment is
    a last resort for a non-obvious invariant or security subtlety — one short
    line above the exact line it explains.
18. Tests: one scenario per test; cover mutation edge cases (missing ids), and
    critical invariants (tenant/data isolation, idempotency/dedup) explicitly.
    Every test module imports `tests.sandbox` before any app import — it pins the
    suite to a throwaway SQLite file, because `load_dotenv()` otherwise finds the
    repo `.env` from anywhere and points the run at the production database.
19. Formatting: EOF newline; lint and format clean before merge.

---

## 7. Good habits / smells to avoid

**Do**

- Clear layering; framework types only at the edges.
- Single source of truth for validation and errors.
- Correct HTTP status codes and REST semantics.
- Run typecheck/lint/tests before pushing when available.

**Avoid**

- Fat routers with business logic; passing framework request objects into services/repos.
- Inconsistent JSON/error shapes; trusting body/query without validation.
- Plaintext passwords stored/returned/logged; committed secrets.
- Unprotected private routes; authorization failures that return data or a fake `404`.
- Identity taken from the request body.
- Cross-domain service calls that bypass orchestrators.
- Frontend features importing each other's internals.
- Views that call `fetch` directly and own auth headers.
- Giant `app.js` / `views.py` that mix HTTP, business rules, and SQL.

---

## 8. What this document deliberately does **not** require

These were useful in a NestJS + React + TypeScript codebase; they are **not**
mandated here:

- Nest modules, `@Injectable`, pipes, guards, Symbol DI tokens
- React components-as-folders, hooks, Context, container `*Container.tsx`
- Tailwind `*.styles.ts` / `.tsx` file taxonomy
- TypeScript `interface` vs `type`, `no any`, `ReturnType<>`

Reuse the **responsibility splits**; choose Python/vanilla idioms for the machinery.

---

## 9. Minimal checklist for a new endpoint + UI

1. Add/adjust the OpenAPI (or shared) contract and error codes.
2. Repository method(s) for persistence.
3. Service method(s) for domain rules.
4. Orchestrator `execute(...)` for authorize → validate → act → map.
5. Thin router that only delegates.
6. Frontend `api.js` action + shared client error mapping.
7. State/wiring update + view update in the owning feature.
8. Tests for happy path + authz + at least one mutation edge case.
