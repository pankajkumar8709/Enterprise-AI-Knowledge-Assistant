# Phases 0–9 — What was built, phase by phase

> A complete walkthrough of the **Enterprise AI Knowledge Assistant**: what each phase set out to do, how it is implemented on the **backend** (FastAPI + PostgreSQL + pgvector) and on the **frontend** (React 18 + TypeScript + Vite), and how the phases connect.
>
> Companion documents: [`build_plan.md`](../build_plan.md) (master spec) · [`docs/CHANGELOG.md`](CHANGELOG.md) (detailed change log per phase) · [`docs/AS_BUILT.md`](AS_BUILT.md) (as-built inventory) · [`docs/AUDIT_0-5.md`](AUDIT_0-5.md) (audit & fixes).

---

## Table of contents

| Phase | Title | Status |
|---|---|---|
| [0](#phase-0--planning--architecture) | Planning & Architecture | ✅ Done |
| [1](#phase-1--backend-foundation) | Backend Foundation | ✅ Done |
| [2](#phase-2--document-management) | Document Management | ✅ Done |
| [3](#phase-3--text-extraction--cleaning) | Text Extraction & Cleaning | ✅ Done |
| [4](#phase-4--chunking--metadata) | Chunking & Metadata | ✅ Done |
| [5](#phase-5--okf-knowledge-extraction) | OKF Knowledge Extraction | ✅ Done (regex → LLM deferred) |
| [5.5](#phase-55--enabling-work-for-rag) | Enabling work for RAG | ✅ Done |
| [6](#phase-6--embeddings--semantic-search) | Embeddings & Semantic Search | ✅ Done |
| [7](#phase-7--query-classification--hybrid-retrieval) | Query Classification & Hybrid Retrieval | ✅ Done |
| [8](#phase-8--llm-answer-generation) | LLM Answer Generation | ✅ Done |
| [9](#phase-9--frontend--react-ui) | Frontend / React UI | ✅ Done (Playwright pending) |

---

## Phase 0 — Planning & Architecture

**Goal:** decide *what* we are building and *how*, before writing code.

### Backend / system design decisions
- **Problem statement & users:** two personas only — **Admin** (uploads documents, reviews knowledge, manages users) and **Employee** (asks questions, reads approved knowledge).
- **Knowledge routing rule:** information is split between
  - **OKF (Organizational Knowledge Format)** — discrete, structured facts (policies, employees, departments, products, FAQs, business rules, assets) that must be *reviewed* before use, and
  - **RAG chunks** — raw document passages used for grounding long-form answers.
- **Target architecture** (documented in `build_plan.md`): upload → validation → extraction → cleaning → chunking → embeddings → vector DB → retrieval → LLM → grounded answer, with ACL (access control) applied at *every* stage.
- **Recorded technology decisions:** FastAPI + PostgreSQL (with **pgvector**) backend, Python 3.13, integer PKs (not UUIDs), local file storage, LLM via **Groq** (OpenAI-compatible), embeddings via `BAAI/bge-small-en-v1.5` (384-dim).
- **Plan documents:** `build_plan.md` (phases + acceptance criteria), `phase0-5.md` (audit plan with a fixed severity scale P0–P3 and an "evidence required" rule).

### Frontend
Nothing yet — the frontend plan (§13 of `build_plan.md`) was written at this stage: React 18 + TypeScript strict + Vite + Tailwind, with design tokens and route guards defined up front so later phases code against a known UI contract.

---

## Phase 1 — Backend Foundation

**Goal:** a secure, production-shaped FastAPI service with auth, roles, and clean infrastructure.

### Backend implementation
- **Scaffold:** app factory in `app/main.py`; routers mounted under `/api/v1` (`auth`, `users`, `documents`, `knowledge`, `chat` stub, `health`).
- **Config:** `app/core/config.py` uses **pydantic-settings** — every knob is an env var (`DATABASE_URL`, `JWT_SECRET` required, ≥32 chars, no defaults), failing fast with a clear error.
- **Database:** SQLAlchemy 2.0 (sync engine, session per request via `yield` + close), **Alembic** migrations, PostgreSQL in production / SQLite in the test suite.
- **Auth:** JWT **HS256** access tokens; bcrypt (cost 12) password hashing; password policy (≥10 chars, 1 uppercase, 1 digit); case-insensitive duplicate email → 409; **identical 401 body** for unknown-email vs wrong-password (no user enumeration); signup can never create an admin (client `role` ignored).
- **RBAC:** two roles (`admin`, `employee`); the role is **re-read from the DB on every request** plus an `is_active` check, so a demoted/deactivated user loses access immediately even with a live token.
- **Error contract & observability:** one JSON error shape, no stack traces leaked; `X-Request-ID` middleware; structured logging; CORS restricted to configured origins; `/health` (liveness) and `/health/ready` (readiness, 503 when DB is down).
- **Refresh tokens:** `refresh_tokens` table with rotation, `POST /auth/refresh` and `/auth/logout` (added during the 0–5 remediation).

### Frontend
Not applicable in this phase — the UI ships in Phase 9.

---

## Phase 2 — Document Management

**Goal:** admins can upload real enterprise documents safely; the system tracks them through a processing lifecycle.

### Backend implementation
- **Upload validation** (`app/api/routes/documents.py`, `app/services/documents.py`):
  - Extension **and** content validated by **magic bytes**, so an `.exe` renamed to `.pdf` is rejected with `415`.
  - Size limit enforced **while streaming** to disk → `413`, never a full-file RAM load.
  - Empty files → `422`; duplicate content detected by **SHA-256** → `409` (with a `?force` override).
  - Stored filename is a generated **UUID** (path traversal impossible); the original name is kept only as metadata; files live in `storage/documents/`, never in a web-served directory.
- **Lifecycle:** `uploaded → processing → ready / failed` with a per-document **status endpoint** and progress reporting; failed processing sets a readable `error_message` and never leaves a document stuck in `processing`.
- **Metadata:** title, original filename, mime, size, sha256, uploader FK, version, timestamps — all in the `documents` table.
- **Deletion:** removes the DB rows (chunks, sources via cascade), the file on disk and the extraction directory — zero orphans; knowledge objects that lose their only source are **archived**, not hard-deleted.
- **Audit:** upload / update / delete / ACL-change events are written to `audit_logs`.

### Frontend
Nothing yet.

---

## Phase 3 — Text Extraction & Cleaning

**Goal:** turn PDF/DOCX/PPTX/TXT/MD bytes into reliable, per-page, Unicode-safe text.

### Backend implementation (`app/services/extraction/`)
- **PDF:** pypdf, page-by-page (1-based page numbers preserved); **OCR fallback** per page (only when a page yields no text; requires Tesseract), so a mixed text/scanned PDF gets OCR exactly where needed. A missing OCR toolchain fails loudly with `failed` + explicit message instead of silently producing empty text.
- **DOCX:** stdlib `zipfile` + `ElementTree` (no heavy dependency) — paragraph order, **Heading 1/2 structure, lists and table cells** all preserved.
- **PPTX:** natural numeric slide order, slide title + body + **speaker notes**, slide number used as the page.
- **TXT/MD:** UTF-8 with an encoding ladder for non-UTF-8 input; Markdown headings become section markers.
- **Empty/corrupt/encrypted documents** → `failed` with distinct, readable error codes (`EMPTY_OR_UNREADABLE_DOCUMENT`, etc.); the worker survives and processes the next job.
- **Cleaning** (the most error-prone step, covered by unit tests):
  - Header/footer/page-number lines removed **only** when repeated on >40% of pages.
  - **Content preservation guaranteed by tests:** `12 days`, `₹5,000`, `15/03/2025`, percentages, emails, URLs survive.
  - Hyphenated line-wraps rejoined only when they form a plausible word; real hyphens (`full-time`) kept.
  - Control/zero-width characters stripped; **₹, em-dash, smart quotes, emoji, Devanagari kept**; idempotent (same input → same output).
- **Raw + cleaned text** are both stored (`storage/extractions/{doc_id}/raw.txt`, `clean.txt`) and retrievable through the API for debugging.

### Frontend
Nothing yet (the extracted-text tab in the admin UI arrives with Phase 9).

---

## Phase 4 — Chunking & Metadata

**Goal:** split cleaned text into retrieval-sized chunks with accurate metadata.

### Backend implementation (`app/services/chunking/`)
- **One production strategy: section-based** (the audit collapsed three overlapping strategies into one). Sections are detected from headings; every chunk carries its section title.
- **Token-aware sizes** via `tiktoken` (char-based fallback): target/max/min from config; no chunk exceeds the max, contiguous `chunk_index` from 0, overlap only in the forced token-split fallback path.
- **No text lost:** a unit test proves every long sentence appears in some chunk; no mid-sentence cuts except oversized-sentence splits.
- **Metadata completeness:** `token_count`, `page_start`/`page_end` (verified against the PDF), section title, source filename, upload date, and **ACL fields copied from the document onto every chunk** (`visibility`, `department_ids`).
- **Idempotent:** re-chunking deletes old chunks first — no duplicates; a unique constraint on `(document_id, chunk_index, …)` backstops it.
- Chunk preview is exposed through an admin-only, paginated endpoint.

### Frontend
Nothing yet.

---

## Phase 5 — OKF Knowledge Extraction

**Goal:** extract discrete, *trustable* facts from documents into the OKF schema.

### Backend implementation (`app/services/knowledge.py`, `app/services/okf/`, `app/api/routes/knowledge.py`)
- **Typed schema:** 7 object types (policy, employee, department, product, faq, business_rule, asset) with **required attributes enforced by a Pydantic validator**; closed relation-predicate list; canonical key = `type + ":" + slug(name)`.
- **Provenance:** every object carries ≥1 **source row** (`okf_sources`: document, chunk, page, **verbatim quote**). A validator checks the quote is literally present in the chunk text — hallucinated values are dropped.
- **Versioning:** a changed fact creates a **new pending version**; approved versions are never silently overwritten; a partial unique index guarantees ≤1 live object per key; superseding archives the old row.
- **Review workflow (a P0 security fix):** extracted objects start `pending_review` and are **invisible to employees until an admin approves** them. Endpoints: approve / reject / **bulk review** (`POST /knowledge/bulk-review`, which also writes a compact audit row).
- **Search API:** exact / partial / typo-tolerant name search plus attribute lookup, ACL-enforced.
- In this phase, extraction ran on **regex heuristics** (Q:/A:, Department:, Employee:, must/should lines → business_rule); the LLM extractor path was deliberately left behind the `LLM_EXTERNAL_ALLOWED` gate for later phases.
- Deleting a document archives sole-source objects and detaches multi-source ones.

### Frontend
Nothing yet.

---

## Phase 5.5 — Enabling work for RAG

**Goal:** everything Phases 6–8 need but Phases 0–5 didn't yet provide.

### Backend implementation
1. **ACL propagation:** `visibility` (`all` / `department`) + `department_ids` on documents, chunks *and* knowledge objects; a single reusable SQL clause (`services/retrieval/acl.py`) applied **inside** every retrieval query; changing document ACL propagates in one transaction. Departments table + `users.department_id` added.
2. **Async ingestion:** the pipeline became a staged background job (FastAPI background task executor — Celery/Redis deliberately deferred): `upload → 202` + poll the status endpoint; retries with 30/120/480 s backoff; `ingestion_jobs` table; idempotent re-runs.
3. **Audit service:** `audit_logs` + one `record_audit()` helper instrumenting auth, document, knowledge and ACL events.
4. **pgvector installed** into PostgreSQL 18 and the schema extended: `document_chunks.embedding vector(384)` with an **HNSW cosine index** (`m=16, ef_construction=64`), `tsv` full-text columns (GIN-indexed), `knowledge_objects.search_tsv` (generated), trigram + jsonb-path indexes.
5. Migration hygiene: `alembic check` clean (no model/migration drift); up/down/up verified on a copy of live data.

### Frontend
Nothing yet.

---

## Phase 6 — Embeddings & Semantic Search

**Goal:** make chunks searchable by meaning, not just keywords.

### Backend implementation
- **`app/services/embeddings.py`:** lazy-loaded **SentenceTransformer** (`BAAI/bge-small-en-v1.5`, 384-dim, L2-normalized); `embed_texts`, `embed_query`, `embed_chunk_text` (chunk text prefixed with document title + section — spec §7.3 step 6); `embed_document_chunks` wired into the ingestion pipeline between chunking and indexing; `python -m app.cli backfill-embeddings` for existing data.
- **`app/services/retrieval/vector.py`:** pgvector HNSW cosine-distance query with `hnsw.ef_search = 100`, ACL clause inside SQL, minimum-similarity floor.
- **`app/services/retrieval/fulltext.py`:** Postgres FTS (`websearch_to_tsquery` + `ts_rank_cd`), ACL-enforced, graceful no-op on SQLite for tests.
- **`app/services/retrieval/fusion.py`:** **Reciprocal Rank Fusion (RRF)** merges vector + FTS results; cosine similarity back-filled for FTS-only hits.
- **API:** `POST /search/semantic` — hybrid search endpoint returning similarity, fts_rank and rrf_score per result.

### Frontend
Nothing yet.

---

## Phase 7 — Query Classification & Hybrid Retrieval

**Goal:** route each user question to the right knowledge source and build the best possible context.

### Backend implementation
- **`app/services/classifier.py`:** LLM classifier (temperature 0) labels each query `structured` / `document` / `mixed` with confidence + entity hints; any failure, bad JSON or low confidence **falls back to `mixed`** (fail-open to the broadest route).
- **`app/services/query_rewrite.py`:** follow-up questions ("and what about low-risk changes?") are rewritten into standalone questions using the last `CHAT_HISTORY_TURNS` messages; falls back to the raw query on any failure.
- **`app/services/retrieval/okf_search.py`:** OKF search scoring `0.5*trgm + 0.4*fts + 0.1*type_boost` (pg_trgm + tsvector), validity-window filter, ACL in SQL, 1-hop relation expansion for the top hits.
- **`app/services/retrieval/merger.py`:** route weighting (OKF ×1.15 for structured, chunks ×1.10 for document), near-duplicate chunk removal (>95% word overlap), OKF deduplication, context token-budget trim, and assignment of citation refs **S1…Sn**.
- **`app/services/retrieval/orchestrator.py`:** one `retrieve()` entry point wiring rewrite → classifier → vector+FTS → OKF → merger, with a **safety net**: a structured query that finds 0 OKF facts also runs RAG.
- **API:** `POST /search/okf` — OKF knowledge search with type-hint filters, ACL-enforced.

### Frontend
Nothing yet.

---

## Phase 8 — LLM Answer Generation

**Goal:** turn retrieved context into a grounded, cited answer with honest fallback.

### Backend implementation
- **Persistence** (`app/models/conversation.py`): `conversations`, `messages` (enum `message_role`), `message_sources` (enum `chat_route`) with FK cascades and indexes (migration `20261006_0010`).
- **`app/services/llm.py`:** Groq SDK wrapper — temperature/timeout from config, exponential-backoff retries on 429/5xx, token accounting, `LLMUnavailableError` on hard failure (surfaces as **503** to the client).
- **`app/services/prompts.py`:** the fixed `ANSWER_SYSTEM` prompt (spec §10.1) and `build_user_message()` rendering OKF facts as `key: value` lines and chunks as labelled passages inside `<context>`.
- **`app/services/answer.py`:** the full pipeline — prompt build → LLM call → `INSUFFICIENT_CONTEXT` detection (the honest "couldn't find this in company knowledge" fallback) → citation-marker parsing/cleaning (drops markers referencing absent sources; normalizes GPT-OSS's full-width `【S1】` to `[S1]`) → confidence → persist user + assistant messages + `message_sources` → audit `chat.query`.
- **`app/services/confidence.py`:** `0.7*top_cited_score + 0.3*min(1, n_distinct_cited/2)` with high/medium/low labels.
- **`app/api/routes/chat.py`:** conversation CRUD (`POST/GET/DELETE /chat/conversations`, get with history) and `POST /chat/conversations/{id}/messages` returning the `ChatAnswerSchema` (answer, route, confidence, latency, sources). Conversations are **auto-titled** from the first message.

### Frontend
Nothing yet (the UI that consumes these endpoints ships in Phase 9).

---

## Phase 9 — Frontend / React UI

**Goal:** a complete React SPA for both personas, built to the §13 spec.

### Frontend implementation (`frontend/`)
- **Stack:** React 18.3 + TypeScript 5.7 **strict (zero `any`)**, Vite 6, Tailwind 3.4 with design tokens, TanStack Query 5 (all server state; `staleTime` 30 s), Zustand 5 (auth store persisted to `kb-auth`), react-hook-form + zod, react-markdown + remark-gfm, lucide-react icons, self-hosted `@fontsource` fonts.
- **Primitives:** 20 `components/ui` building blocks (Button, Modal, Drawer, Table, Toast, Skeleton, ConfirmDialog, …) with focus-trapping overlays, global focus ring and `prefers-reduced-motion` support; a `/dev/ui` gallery page.
- **Layout & guards:** sidebar (icon rail on small screens, drawer on mobile), sticky topbar with account menu, `RequireAuth` and `RequireRole` (an employee hitting `/admin/*` gets an explicit 403 page).
- **Auth UI:** login/signup with zod inline validation, password reveal, `?expired=1` banner; the axios client **refreshes the access token once** on 401 (single-flight across concurrent requests) and otherwise clears the session and lands on `/login?expired=1`.
- **Chat page** (`pages/app/Chat.tsx`, `components/chat/`):
  - Optimistic user bubble + "Searching company knowledge…" skeleton; **route + confidence badges**; markdown answers with inline **`[S#]` citation chips**; collapsible per-message sources and a **source drawer** showing document, section, page and the verbatim passage.
  - **Conversation history as a right-side panel** (`components/chat/ConversationList.tsx` in `ChatWindow.tsx`): docked sticky panel on desktop, slide-in drawer on mobile; **New chat** button (which also clears any un-sent draft via `hooks/useChat.ts` so the next message truly starts a new conversation), conversation switching with full history restore, confirm-delete.
  - Auto-grow composer (Enter sends / Shift+Enter newline / 1800-char counter), retryable error card, unanswerable-info card, suggestion cards on the empty state.
- **Admin console** (`pages/admin/`): dashboard (stat cards, recent uploads, needs-attention list); documents list with 3-second per-row status polling, filters and an upload modal (drag-drop, visibility, conditional department multi-select, 25 MB guard); document detail tabs (Overview / Extracted text / Chunks / Knowledge) with ACL editing and new-version upload; knowledge list, **review queue** (verbatim quote, confidence bar, bulk approve/reject) and knowledge detail (attributes, relations, provenance, versions); users & departments; audit logs with filters.
- **Library:** ACL-filtered document card grid with search and download.
- **Data rules:** mutations invalidate affected query keys; toasts surface backend error messages; every list ships Skeleton + EmptyState + ErrorState.
- **Quality gates:** `tsc --noEmit` 0 errors, ESLint 0 problems, production build succeeds; verified end-to-end in the browser (signup → auto-login, grounded answers with citations, unanswerable path, token-expiry flow, ACL filtering, employee 403, responsive at 375/768/1280 px).

### Backend changes made during Phase 9 verification
- **Env-managed administrator:** `ADMIN_EMAIL` / `ADMIN_PASSWORD` provision and synchronize one marked admin (`is_bootstrap_admin`) at startup.
- Login with an unrecognized stored hash fails closed as 401 (was a 500).
- OKF minimum score lowered 0.30 → 0.25 after a live grounded-answer regression.
- Full-width citation markers (`【S1】`) normalized before source validation.
- Read model tolerates legacy out-of-list relation predicates (was a 500 on `GET /knowledge`).

---

## How it all fits together

```text
                    ┌─────────────────────────────┐
                    │   React SPA (Phase 9)       │
                    │  chat · admin · library     │
                    └──────────────┬──────────────┘
                                   │ axios + TanStack Query (JWT, auto-refresh)
                                   ▼
                    ┌─────────────────────────────┐
                    │   FastAPI (Phases 1–8)      │
                    │  auth · RBAC · ACL · audit  │
                    └──────────────┬──────────────┘
              ┌────────────────────┼─────────────────────┐
              ▼                    ▼                     ▼
      Ingestion pipeline     Retrieval (Ph 6–7)    Answering (Ph 8)
      upload → validate      rewrite → classify    prompts → Groq LLM
      → extract → clean      → vector+FTS+RRF      → citations → confidence
      → chunk → embed        → OKF search          → conversations persisted
              │                    │                     │
              └────────────────────┴─────────────────────┘
                                   ▼
                    PostgreSQL 18 + pgvector + pg_trgm
              (documents, chunks+embeddings, OKF, chat, audit)
```

- **Everything is ACL-filtered in SQL** — an employee can never retrieve a chunk, fact, document or conversation their department cannot see.
- **Nothing unreviewed is trusted** — OKF objects answer questions only after an admin approves them.
- **No answer without sources** — the LLM must cite `[S#]` refs assigned by the merger; markers without a matching source are stripped, and questions the corpus can't answer get the honest fallback instead of a hallucination.

## Remaining known gaps

- Playwright E2E suite and Lighthouse run (Phase 9 acceptance criteria) not yet done.
- XLSX extraction and document version upload UI polish are on the roadmap.
- Celery/Redis executor swap for ingestion (currently FastAPI background tasks) is deferred by design.
- Frontend main bundle (761 kB) is not yet code-split.
