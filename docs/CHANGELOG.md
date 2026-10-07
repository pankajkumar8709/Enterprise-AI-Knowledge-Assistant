# Changelog

All notable changes to the Enterprise AI Knowledge Assistant backend.

## [Unreleased] — Phase 9 Frontend (2026-10-06)

Implements `build_plan.md` §13 (React 18 + TypeScript strict + Vite + Tailwind) under `frontend/`.

### Added

- **Scaffold**: Vite 6 + React 18 + TS strict, `tailwind.config.ts` design tokens (§13.1),
  `@fontsource` Inter/JetBrains Mono (no CDN), `@tailwindcss/typography`, global visible
  focus ring and `prefers-reduced-motion` handling, `@/*` path alias.
- **20 `components/ui` primitives** (Button, Card, Badge, Input, Textarea, Select, Modal,
  Drawer, Tabs, Table, Skeleton, Spinner, Toast, EmptyState, ErrorState, ProgressSteps,
  StatCard, Tooltip, ConfirmDialog, Avatar) with focus-trapping overlays, plus the
  `/dev/ui` component gallery.
- **Layout & guards**: sidebar (icon rail < `lg`, drawer < `md`), sticky topbar with account
  menu, `RequireAuth`, `RequireRole` (employees get an explicit 403 page).
- **Auth**: 2-column Login/Signup with zod inline errors, password reveal and the
  `?expired=1` banner; Zustand store persisted to `kb-auth`; axios client that refreshes the
  access token **once** on 401 (single-flight across concurrent requests) and otherwise
  clears the session, toasts, and lands on `/login?expired=1`.
- **Chat (§12.2)**: optimistic user bubble + "Searching company knowledge…" skeleton, route
  and confidence badges, inline `[S#]` citation chips, collapsible sources, right-hand source
  drawer, follow-ups, unanswerable info card, retryable error card, auto-grow composer
  (Enter sends / Shift+Enter newline / counter at 1800), conversation sidebar with
  confirm-delete.
- **Admin console (§12.1)**: dashboard (4 stat cards, recent uploads, needs attention);
  documents with 3 s per-row status polling, filters and upload modal (drag-drop, title
  prefill, visibility, conditional department multi-select, 25 MB guard); document detail
  tabs (Overview / Extracted text / Chunks / Knowledge) with ACL edit and new-version upload;
  knowledge list, review queue (verbatim quote, confidence bar, bulk approve/reject) and
  knowledge detail (attributes, relations, provenance, versions); users & departments; audit
  logs with action/user/date filters.
- **Library (§12.2.9)**: ACL-filtered card grid with search and download.
- **Data rules**: TanStack Query only (`staleTime` 30 s, status polling `refetchInterval`
  3 s), mutations invalidate affected keys, toasts surface `ApiError.error.message`, and every
  list/table ships Skeleton + EmptyState + ErrorState.

### Fixed (found while verifying Phase 9 end to end)

- **Env-managed administrator** — `ADMIN_EMAIL` and `ADMIN_PASSWORD` now
  provision/synchronize one marked admin account at startup. Email/password
  changes update that account; conflicting email ownership fails startup.
- **`app/services/auth.py`** — an unrecognized stored password hash previously
  raised Passlib `UnknownHashError` and returned HTTP 500 on login. It now logs
  the affected user ID and fails closed through the standard 401 invalid-credentials
  response; the account still needs a password reset.
- **`app/core/config.py`** — lowered the default OKF minimum score from `0.30`
  to `0.25`. An approved employee fact matching “Who is the HR manager?” scored
  `0.2809` and was discarded just below the old threshold, causing the grounded
  answer fallback despite relevant approved knowledge being present.
- **`app/services/answer.py`** — GPT-OSS emits citations as `【S1】`, while the
  parser only recognized `[S1]`. Full-width citation markers are now normalized
  to `[S#]` before source validation so cited-source metadata and UI links work.
- **`app/services/knowledge.py`** — legacy `knowledge_objects.relations` rows can contain
  predicates outside the §6.2 closed list (`derived_from`, `member_of`, written before the
  validator existed). The read model validated stored values and raised, so `GET /knowledge`,
  `GET /knowledge/search`, `GET /knowledge/{id}` and `/knowledge/{id}/versions` returned
  **500 for every request** against the dev DB. `_as_read_model` now drops unknown predicates
  with a logged warning; input validation is unchanged.
- **`alembic/versions/20261006_0010_phase8_chat.py`** — `op.create_index` duplicated the index
  already emitted by `sa.Column(..., index=True)`, so `alembic upgrade head` failed with
  `DuplicateTable`. Primary-key indexes are now created explicitly (repo convention),
  `message_sources.extra` uses `postgresql.JSONB` to match the model, and imports are sorted;
  `alembic check` reports no drift and the migration round-trips (down/up).
- **Frontend**: every react-hook-form form is `noValidate` so styled zod errors replace the
  browser's native validation bubbles; `Badge` no longer wraps; knowledge/audit/user table
  columns clamp or hide so rows fit.

### Verification

`tsc --noEmit` 0 errors · ESLint 0 problems · no `any` in `src` · `npm run build` succeeds.
Live pass against uvicorn + PostgreSQL 18 using a throwaway account created through signup
and deleted afterwards: signup → auto-login, suggestion-card question (optimistic skeleton →
answer), unanswerable path, client timeout → error card + Retry, conversation confirm-delete,
library ACL filtering, employee → `/admin/*` 403, and every admin page rendered (dashboard,
documents, document detail tabs, knowledge list/review/detail, users, audit logs). Responsive
checked at 375 / 768 / 1280 px. Dev DB migrated to head `20261006_0010`; backend suite
97 passed.

### Not yet done

- Playwright suite and Lighthouse run required by the §14 Phase 9 acceptance criteria.
- Grounded answers (citations, source drawer) could not be exercised: the dev DB has **0
  `document_chunks` rows and 0 approved knowledge objects**, so retrieval correctly returns
  nothing and every answer is the unanswerable fallback.

## [Unreleased] — Phase 8 LLM Answer Generation (2026-10-06)

Implements `build_plan.md` §14 Phase 8.

### Added

- **`app/models/conversation.py`**: `conversations`, `messages`, `message_sources`
  tables with enums `message_role` and `chat_route` (spec §5).
- **`app/services/llm.py`**: Groq SDK wrapper — temperature/timeout from config,
  exponential-backoff retries on 429/5xx (up to `llm_max_retries`), token
  accounting, raises `LLMUnavailableError` on hard failure (spec §10).
- **`app/services/prompts.py`**: Exact `ANSWER_SYSTEM` prompt (spec §10.1) and
  `build_user_message()` rendering OKF facts as `key: value` lines and chunks
  as labelled passages inside `<context>` (spec §10.2).
- **`app/services/confidence.py`**: `compute_confidence()` formula
  `0.7*top_cited_score + 0.3*min(1, n_distinct_cited/2)` and `confidence_label()`
  thresholds high/medium/low (spec §10.3).
- **`app/services/answer.py`**: Full answer pipeline — prompt build → LLM call
  → `INSUFFICIENT_CONTEXT` detection → citation marker parsing/cleaning
  (removes markers referencing absent sources) → confidence → persist user +
  assistant messages + `message_sources` → audit `chat.query` (spec §10.3).
- **`app/api/routes/chat.py`**: Replaced stub with full chat endpoints:
  `POST /chat/conversations` (201), `GET /chat/conversations`,
  `GET /chat/conversations/{id}`, `DELETE /chat/conversations/{id}` (204),
  `POST /chat/conversations/{id}/messages` → `ChatAnswerSchema` (spec §8).
  Auto-titles conversation from first message. Returns 503 on `LLMUnavailableError`.
- **`alembic/versions/20261006_0010_phase8_chat.py`**: Migration creating
  `conversations`, `messages`, `message_sources` with FK cascades and indexes.
- **`tests/test_phase8.py`**: 29 tests covering confidence formula, citation
  parsing, system prompt content, prompt builder, LLM wrapper guard and retry
  detection, answer fallback (no context), mocked LLM happy path,
  `INSUFFICIENT_CONTEXT` response, GPT-OSS full-width citation normalization,
  and all chat API endpoints (auth, CRUD,
  auto-title, message persistence, 503 on LLM error).

### Changed

- **`app/models/__init__.py`**: Added `Conversation`, `Message`, `MessageRole`,
  `MessageSource`, `ChatRoute` exports so `Base.metadata` picks up the new
  tables for SQLite test schema creation.

### Deviations from spec

- LLM provider remains Groq (not Anthropic) per prior human decision.
- Integer PKs kept throughout (not UUID) per prior human decision.

### Verified

- 97 tests pass (69 existing + 28 new); quality gates clean.

---

## [Unreleased] — Phase 7 Query Classification & Hybrid Retrieval (2026-10-06)

Implements `build_plan.md` §14 Phase 7.

### Added

- **`app/services/retrieval/okf_search.py`**: OKF knowledge search — pg_trgm
  similarity + tsvector FTS scoring (`0.5*trgm + 0.4*fts + 0.1*type_boost`),
  validity window filter, ACL inside SQL, 1-hop relation expansion for top-3
  results (spec §9.3). Graceful no-op on SQLite.
- **`app/services/classifier.py`**: LLM-based query classifier (temperature 0)
  outputting `structured / document / mixed` with confidence and entity hints.
  Falls back to `mixed` on any error, invalid JSON, or confidence below
  `CLASSIFIER_MIN_CONFIDENCE` (spec §9.5). No-op when `LLM_EXTERNAL_ALLOWED=false`.
- **`app/services/query_rewrite.py`**: Follow-up query rewriter using the last
  `CHAT_HISTORY_TURNS` messages to produce a standalone question (spec §9.4).
  Falls back to the raw query on any failure or when LLM is disabled.
- **`app/services/retrieval/merger.py`**: Context merger — route weighting
  (OKF ×1.15 for structured, chunk ×1.10 for document), near-duplicate chunk
  removal (>95% word overlap), OKF deduplication, context token budget trim,
  ref assignment S1…Sn (spec §9.6).
- **`app/services/retrieval/orchestrator.py`**: Single `retrieve()` entry point
  wiring rewrite → classifier → vector+FTS → OKF → merger. Safety net: structured
  route with 0 OKF hits also runs RAG (spec §9.5). Returns `RetrievalResult`.
- **`app/api/routes/search.py`**: Added `POST /search/okf` endpoint — OKF
  knowledge search with type_hints filter, ACL-enforced, returns scored results
  with relation metadata.
- **`tests/test_phase7.py`**: 25 tests covering classifier parse/fallback,
  query rewrite passthrough, merger deduplication/weighting/budget/refs,
  OKF search SQLite no-op, orchestrator happy path and structured safety net,
  and both search API endpoints (auth, empty query, employee access).

### Fixed

- **`app/services/retrieval/vector.py`**: Added SQLite dialect guard before
  `SET LOCAL hnsw.ef_search = 100` — this PG-only statement crashed the test
  suite when the search endpoints were called against the SQLite test DB.

### Verified

- 69 tests pass (44 existing + 25 new); quality gates clean.

## [Unreleased] — Phase 6 Embeddings & Semantic Search (2026-10-06)

Implements `build_plan.md` §14 Phase 6.

### Added

- **`app/services/embeddings.py`**: lazy `SentenceTransformer` model loader
  (`BAAI/bge-small-en-v1.5`, 384 dims, L2-normalised), `embed_texts`,
  `embed_query`, `embed_chunk_text` (document title + section prefix per
  spec §7.3 step 6), `embed_document_chunks` (ingestion hook), and
  `backfill_embeddings` (CLI helper).
- **`app/services/retrieval/vector.py`**: HNSW cosine-distance query with
  `hnsw.ef_search=100`, ACL clause applied inside SQL, `MIN_SIMILARITY` floor.
- **`app/services/retrieval/fulltext.py`**: `websearch_to_tsquery` + `ts_rank_cd`
  FTS query with ACL; graceful no-op on SQLite (tests).
- **`app/services/retrieval/fusion.py`**: Reciprocal Rank Fusion (RRF) merging
  vector and FTS results; cosine similarity back-filled for FTS-only hits;
  returns enriched `ChunkResult` dataclasses.
- **`app/api/routes/search.py`**: `POST /search/semantic` — hybrid search
  endpoint, ACL-enforced, returns top-k results with similarity/fts_rank/rrf_score.
- **`app/cli.py`**: `python -m app.cli backfill-embeddings` command to embed
  all existing chunks without re-ingesting documents.
- **`requirements.txt`**: added `sentence-transformers==3.4.1`, `tiktoken==0.9.0`,
  `pgvector==0.3.6`.

### Changed

- **`app/services/ingestion.py`**: embedding stage wired into `_run_pipeline`
  between chunking and indexing (spec §7.2).
- **`app/api/router.py`**: search router mounted at `/search`.

### Fixed

- `HTTP_413_CONTENT_TOO_LARGE` → `HTTP_413_REQUEST_ENTITY_TOO_LARGE` and
  `HTTP_422_UNPROCESSABLE_CONTENT` → `HTTP_422_UNPROCESSABLE_ENTITY` in
  `documents.py` and `knowledge.py` (Starlette 1.7 renamed these constants).

### Verified

- 44 tests pass; quality gates clean.

## [Unreleased] — Phase 5.5 completion (2026-10-06)

Closes the six enabling items of `build_plan.md` §Phase 5.5 (see
[`AS_BUILT.md`](AS_BUILT.md) §8 for the per-item state and evidence).

### Added

- **#6 Vector/full-text schema**: pgvector **0.8.6 installed** into the local
  PostgreSQL 18 host; migrations/models declare `document_chunks.embedding
  vector(384)` (HNSW, cosine), `tsv` and `knowledge_objects.search_tsv`
  (generated, GIN-indexed), trigram and jsonb-path indexes for §9 retrieval,
  and the chunk `(document_id, version)` index. Migration `20261005_0009`.
- `.env` connection string fixed to a role that authenticates; the app now
  boots against the dev database (`/health/ready` → `database: connected`).

### Fixed

- **Tests restored to green (44 passed)**: ingestion retry backoff is
  neutralized in tests as the pipeline comment always intended (failed ingests
  no longer sleep 30/120/480 s inside requests), and 14 test expectations were
  updated to the §7.1.5 async contract (202 + poll §8 status endpoint).
- Chunking no longer collapses explicit small `chunk_size` runs into one
  chunk: the token floor is capped by the largest draft the requested size
  actually produces (chars/4 undercounted tokens for prose).
- Migration `20261005_0008` downgrade drops `documents.uploaded_by_id`;
  `alembic downgrade` + re-`upgrade` now succeeds on a data copy.
- Model/migration drift resolved (`alembic check` clean): `tsv`/`search_tsv`
  columns and PG retrieval indexes declared in models; `refresh_tokens.token_hash`
  uniqueness matches the migration's named unique constraint.
- `ruff check`, `ruff format --check` and `mypy app` are clean again
  (admin stats/analytics annotations, `TokenUser` response typing, structlog
  processor list typing).

### Verified

- Migrations `0007 → 20261005_0009` apply to a copy of the live data
  (up/down/up clean, data intact); dev DB migrated to head.
- Full test suite (44) + quality gates green; Postgres smoke:
  boot + `/health` + `/health/ready` against the migrated dev DB.

## [Unreleased] — Phase 0–5 audit remediation (2026-10-05)

Remediation of every finding in [`docs/AUDIT_0-5.md`](AUDIT_0-5.md)
(P0 ×4, P1 ×23, P2 ×16, P3 ×3). One regression test per P0/P1 finding
(`tests/test_phase0_5_fixes.py`); one commit per finding per the audit rules.

### Security

- **F-004** Removed the database password from tracked config: `alembic.ini`
  now takes its URL from the environment (via `alembic/env.py`) and the
  previously committed scratch `testpg.py` reads `PGPASSWORD` from the env.
- **F-025** Bumped pins for packages that parse untrusted uploads:
  `pypdf 4.3.1 → 6.19.0`, `Pillow 10.4.0 → 12.3.0`,
  `python-multipart 0.0.20 → 0.0.32`, `fastapi 0.116.1 → 0.142.2`,
  `starlette → 1.7.0`, `cryptography → 50.0.2`, `pytest → 9.0.3`.
  `pip-audit` dropped from **150 rows / 8 packages** to **2 rows / 1 package**
  (remaining `ecdsa` advisory has no fix and is unreachable on our HS256 path).
- **F-001** Knowledge review workflow + ACL: extracted facts are
  `pending_review` and invisible to employees until an admin approves them;
  `GET /knowledge/{id}` enforces the visibility clause.
- Department ACL (`visibility`, `department_ids`) added to documents, chunks
  and knowledge objects; `department` visibility restricts employees to their
  own department.
- Audit logging (`audit_logs`) for auth, document and knowledge events.

### Fixed

- **F-002** Invalid uploads no longer return `500` or get stuck in
  `processing`: extraction failure marks the document `failed` with a status
  endpoint and progress reporting.
- **F-003** Text cleaner preserves currency (₹), em-dash, smart quotes,
  emoji and Devanagari while still stripping control/zero-width characters;
  idempotent.
- **F-016** PPTX extraction uses natural numeric slide order and includes
  speaker notes.
- Header/footer removal now requires the >40% repetition threshold.
- Chunking produces one production strategy (section-based), contiguous
  indices from 0, `token_count` within limits, and copies ACL metadata.
- Knowledge versioning: exactly one live object per key (partial unique index
  over `pending_review`/`approved`); superseding a fact archives the old row.
- `DELETE /knowledge/{id}` and deleting a document archive knowledge instead
  of hard-deleting, leaving no orphans.
- Document status is server-derived (no longer client-writable);
  `PATCH /users/{id}` and pagination envelopes added.

### Tooling

- **F-028** Added `pyproject.toml` configuring `ruff` (allows FastAPI
  `Depends`/`Query` in defaults); `ruff check app tests` and
  `ruff format --check app tests` are clean.
- **F-029** `mypy app --ignore-missing-imports` is clean.
- **F-041** Reviewed `ElementTree` usage annotated with `# nosec B314`;
  `bandit -r app -ll` reports 0 high / 0 medium.
- **F-030** Added `.env.example`, `docs/AUDIT_0-5.md`, `docs/AS_BUILT.md`,
  `docs/openapi.json`, this changelog, and refreshed the README status.
