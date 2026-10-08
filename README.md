# 🤖 Enterprise AI Knowledge Assistant

> A secure, full-stack enterprise AI platform: document ingestion, knowledge extraction, hybrid RAG retrieval, and grounded LLM answers — with a complete React frontend.

The **Enterprise AI Knowledge Assistant** is a full-stack project that gives organizations a centralized platform for managing enterprise knowledge and asking questions in natural language. Every answer is **grounded in the company's own documents and facts**, cites its sources, respects document-level access control, and honestly says when it doesn't know.

The project was built **phase by phase (Phase 0 → Phase 9)** — planning, backend foundation, document pipeline, chunking, knowledge extraction, embeddings, hybrid retrieval, LLM answering, and finally the React frontend. A complete phase-by-phase walkthrough lives in **[docs/PHASES.md](docs/PHASES.md)**.

---

# 🚀 Project Vision

Modern organizations have large amounts of information distributed across:

* 📄 Company documents
* 📚 Policies and guidelines
* 📋 Reports
* 🧑‍💼 HR documents
* 💻 Technical documentation
* 📊 Project information
* 📝 Internal knowledge bases

Finding the right information quickly can be difficult.

This project lets authorized users interact with all of it through natural language:

```text
Enterprise Documents
        ↓
Upload → Validation → Text Extraction → Cleaning
        ↓
Token-aware Chunking → Embeddings (bge-small-en-v1.5, 384-d)
        ↓
PostgreSQL + pgvector (HNSW) + Full-text search (RRF fusion)
        ↓
Query classification + OKF fact search + Context merger
        ↓
Grounded LLM answer with [S#] citations + confidence
        ↓
User (only what their permissions allow)
```

Security and authorization are applied **at every stage** — ACL clauses run inside the SQL of every retrieval query — so users only ever receive information they are allowed to access.

---

# 📌 Current Status

## Phases 0–9 — Complete (frontend + full RAG pipeline)

The repository implements **Phases 0–9 of the build plan** (see
[build_plan.md](build_plan.md), the phase walkthrough in
[docs/PHASES.md](docs/PHASES.md), the audit in [docs/AUDIT_0-5.md](docs/AUDIT_0-5.md)
and the detailed [docs/CHANGELOG.md](docs/CHANGELOG.md)).

### Implemented

**Backend (FastAPI + PostgreSQL)**
* ✅ FastAPI project scaffold, PostgreSQL + SQLAlchemy 2.0, Alembic migrations
* ✅ JWT authentication (HS256, bcrypt, refresh-token rotation, role re-read per request, no user enumeration)
* ✅ Role-based access + ACL: document **visibility** (`all` / `department`) enforced in SQL across documents, chunks and knowledge objects
* ✅ Document ingestion: magic-byte validation, SHA-256 duplicate detection, streaming size limit, `413`/`415`/`422`, async lifecycle (`uploaded → processing → ready/failed`) with status polling and retries
* ✅ Text extraction for **PDF, DOCX, PPTX, TXT, MD** (per-page OCR fallback, unicode-safe cleaner, DOCX headings/lists/tables, PPTX slide order + speaker notes, >40% header/footer threshold)
* ✅ Token-aware section-based chunking (tiktoken counting, contiguous indices, ACL copied onto chunks)
* ✅ OKF knowledge objects: typed schema, verbatim-quote sources, versioning, admin **review workflow** (`pending_review → approved/rejected`), bulk review, archive-on-delete
* ✅ Embeddings + **hybrid retrieval**: pgvector HNSW cosine search, Postgres FTS, Reciprocal Rank Fusion, LLM query classification (`structured/document/mixed`), follow-up query rewriting, context merger with `S1…Sn` citation refs
* ✅ LLM answer generation (Groq): grounded answers with `[S#]` citations, `INSUFFICIENT_CONTEXT` honest fallback, confidence scoring, conversation/message/source persistence, 503 on LLM outage
* ✅ Audit log (`audit_logs`) for auth, document, knowledge and ACL events
* ✅ `/health` + `/health/ready`, CORS, `X-Request-ID` tracing, structured logging, OpenAPI docs
* ✅ Automated tests (97 passing) incl. one regression test per audit P0/P1 finding

**Frontend (React 18 + TypeScript strict + Vite + Tailwind)**
* ✅ Login/Signup with zod validation and single-flight token refresh
* ✅ Chat UI: optimistic sending, route + confidence badges, markdown answers with inline `[S#]` citation chips, source drawer, **right-side conversation history with New chat / switch / delete**
* ✅ Admin console: dashboard, documents (upload modal, live status polling, detail tabs), knowledge review queue (bulk approve/reject), users, departments, audit logs
* ✅ Library page with ACL-filtered document cards, employee 403 page, responsive at 375/768/1280 px
* ✅ `tsc` 0 errors, ESLint 0 problems, production build passes

---

# 🏗️ Architecture

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

---

# 🧩 Technology Stack

| Technology | Purpose |
| ------------------------ | ---------------------------- |
| 🐍 **Python 3.13** | Backend programming |
| ⚡ **FastAPI** | REST API framework |
| 🐘 **PostgreSQL 18** | Relational database |
| 🧭 **pgvector + pg_trgm** | Vector (HNSW) and trigram/FTS search |
| 🗃️ **SQLAlchemy 2.0** | ORM and database interaction |
| 🔄 **Alembic** | Database migrations |
| 🔐 **JWT (python-jose) + bcrypt** | Authentication |
| 🧠 **sentence-transformers** | Embeddings (`BAAI/bge-small-en-v1.5`) |
| 🤖 **Groq SDK** | LLM answer generation & query classification |
| 📄 **pypdf** | PDF text extraction (stdlib XML for DOCX/PPTX) |
| ⚛️ **React 18 + TypeScript (strict)** | Frontend |
| 🟢 **Vite 6 + Tailwind CSS 3.4** | Frontend build & styling |
| 🔄 **TanStack Query 5 + Zustand 5** | Frontend data & state |
| 🧪 **Pytest + Vitest-ready tooling** | Automated testing |
| 📖 **Swagger / OpenAPI** | API documentation |

---

# 📁 Project Structure

```text
Enterprise-AI-Knowledge-Assistant/
│
├── app/                          # FastAPI backend
│   ├── api/routes/               # auth, users, documents, knowledge, search, chat, health, admin
│   ├── core/                     # config, security, deps, exceptions, logging
│   ├── db/                       # base, session
│   ├── models/                   # user, document, chunk, knowledge, conversation, audit
│   ├── schemas/                  # Pydantic request/response models
│   ├── services/                 # ingestion, extraction, chunking, okf, embeddings,
│   │   └── retrieval/            # vector, fulltext, fusion, okf_search, classifier, merger, orchestrator
│   ├── cli.py                    # backfill-embeddings & maintenance commands
│   └── main.py
│
├── frontend/                     # React 18 + TypeScript + Vite + Tailwind (Phase 9)
│   └── src/
│       ├── components/{ui,layout,chat,documents,knowledge}/
│       ├── pages/{app,admin}/    # Chat, Library, admin console pages
│       ├── hooks/                # useAuth, useChat, useDocuments, …
│       ├── lib/                  # axios client (token refresh), constants, format
│       ├── store/                # Zustand auth store
│       └── types/                # shared API types
│
├── alembic/versions/             # 11+ migrations (schema evolution)
├── docs/                         # PHASES.md, CHANGELOG.md, AUDIT_0-5.md, AS_BUILT.md, openapi.json
├── storage/                      # uploaded documents + extraction artifacts (git-ignored)
├── tests/                        # pytest suite (SQLite; PG for retrieval features)
├── build_plan.md                 # master spec
├── phase0-5.md                   # audit plan
├── .env.example                  # every backend env var
├── alembic.ini
├── requirements.txt
└── README.md
```

---

# 🔐 Authentication & Authorization

### JWT Authentication

```text
User → Login → Credentials verified (bcrypt) → JWT access token (+ refresh rotation)
     → Authenticated API requests (role re-read from DB per request)
```

* Signup can never create an admin; duplicate emails → 409; unknown email and wrong password return the identical 401 (no user enumeration).
* Demoted or deactivated users lose access immediately, even with a live token.
* The frontend auto-refreshes the access token once on 401 and otherwise signs the user out to `/login?expired=1`.

### Roles & ACL

* **admin** — uploads documents, reviews knowledge, manages users/departments, sees audit logs.
* **employee** — chats, searches approved knowledge, reads documents their permissions allow.
* Document **visibility** (`all` / `department`) + `department_ids` cascade onto chunks and knowledge objects and are enforced **inside every SQL query**, for both API listings and retrieval.

---

# 📄 Document Pipeline

```text
Upload → magic-byte + size validation (413/415/422) → SHA-256 duplicate check (409)
      → async ingestion (202 + status polling, retries with backoff)
      → per-page text extraction (PDF/DOCX/PPTX/TXT/MD, OCR fallback)
      → unicode-safe cleaning (numbers, ₹, dates, emoji preserved)
      → token-aware section chunking (ACL copied to every chunk)
      → embedding generation (bge-small-en-v1.5, 384-d, HNSW index)
      → ready / failed with readable error messages
```

---

# 💬 Grounded AI Chat

```text
User question
      ↓ Auth / RBAC
Follow-up rewrite (standalone question) + LLM route classification (structured/document/mixed)
      ↓ Hybrid retrieval (pgvector + FTS + RRF) and OKF fact search — ACL in SQL
Context merger (dedup, route weighting, S1…Sn refs, token budget)
      ↓ Groq LLM with fixed grounding prompt
Answer with [S#] citations, route badge, confidence %, latency
      ↓ INSUFFICIENT_CONTEXT → honest "couldn't find this" fallback (never a hallucination)
Conversation + messages + sources persisted per user
```

---

# ⚙️ Setup

## 1. Clone the Repository

```powershell
git clone https://github.com/pankajkumar8709/Enterprise-AI-Knowledge-Assistant.git
cd Enterprise-AI-Knowledge-Assistant
```

## 2. Backend — Virtual Environment & Dependencies

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

## 3. Configure Environment Variables

```powershell
copy .env.example .env
```

Then update `.env`:

```env
DATABASE_URL=postgresql://username:password@localhost:5432/enterprise_ai
JWT_SECRET=change-me-at-least-32-characters-long
GROQ_API_KEY=your-groq-api-key
```

> ⚠️ Never commit `.env`, database credentials, JWT secrets or API keys.
>
> To provision one local administrator from `.env`, set both `ADMIN_EMAIL` and
> `ADMIN_PASSWORD`. The backend creates or synchronizes that account on startup.
> Changing either value takes effect after restarting the backend. Use a strong
> password and keep `.env` out of source control.

## 4. Frontend — Install

```powershell
cd frontend
npm ci
```

---

# 🗄️ Database Setup

The application uses PostgreSQL with SQLAlchemy. Ensure **pgvector** and **pg_trgm** are available, then run the Alembic migrations:

```powershell
alembic upgrade head
```

To embed chunks from documents ingested before Phase 6:

```powershell
python -m app.cli backfill-embeddings
```

---

# ▶️ Run the Application

**Backend** (from the repo root):

```powershell
uvicorn app.main:app --reload
```

The API starts at `http://127.0.0.1:8000`.

**Frontend** (from `frontend/`):

```powershell
npm run dev
```

The UI starts at `http://localhost:5173` (the dev server proxies `/api` to the backend).

---

# 📖 API Documentation

FastAPI automatically generates interactive API documentation.

### Swagger UI

```text
http://127.0.0.1:8000/docs
```

### ReDoc

```text
http://127.0.0.1:8000/redoc
```

A pre-generated `docs/openapi.json` is also committed.

---

# 🧪 Testing

Backend test suite:

```powershell
pytest            # 97 tests
pytest -v         # verbose
```

Frontend checks:

```powershell
cd frontend
npm run typecheck   # tsc --noEmit
npm run lint        # eslint
npm run build       # production build
```

---

# 🩺 Health Checks

* `GET /health` — liveness (public)
* `GET /health/ready` — readiness; returns 503 when the database is unreachable

---

# 📊 Development Roadmap

## Phase 0 — Planning & Architecture
* [x] Problem statement, personas, knowledge-routing rule
* [x] Architecture + data-flow diagrams
* [x] Technology decisions (LLM, embeddings, vector DB, storage)

## Phase 1 — Backend Foundation
* [x] FastAPI scaffold, SQLAlchemy 2.0, Alembic
* [x] JWT auth + refresh-token rotation, RBAC, role re-read per request
* [x] Error contract, request-ID logging, CORS, health endpoints
* [x] Swagger documentation, automated tests

## Phase 2 — Document Management
* [x] Upload with magic-byte validation, streaming size limit, SHA-256 duplicates
* [x] Async lifecycle (`uploaded → processing → ready/failed`) + status endpoint
* [x] Safe storage (UUID names, no path traversal), orphan-free delete
* [ ] XLSX processing

## Phase 3 — Text Extraction & Cleaning
* [x] PDF (per-page OCR fallback), DOCX (headings/lists/tables), PPTX (slides + notes), TXT/MD
* [x] Content-preserving, idempotent cleaner (>40% header/footer threshold)
* [x] Empty/corrupt/encrypted documents fail loudly with clear codes

## Phase 4 — Chunking & Metadata
* [x] Token-aware section-based chunking (tiktoken), no text loss (tested)
* [x] Complete metadata (token_count, pages, section, ACL) + contiguous indices
* [x] Idempotent re-chunking with unique constraint

## Phase 5 — OKF Knowledge Extraction
* [x] Typed OKF schema + closed predicates, verbatim-quote sources
* [x] Versioning (no silent overwrite) + admin review workflow + bulk review
* [x] ACL on knowledge objects; archive-on-delete
* [ ] LLM-based extractor (currently regex heuristics, LLM path gated behind `LLM_EXTERNAL_ALLOWED`)

## Phase 5.5 — RAG enabling work
* [x] ACL propagation across documents/chunks/OKF, departments table
* [x] Async staged ingestion + `ingestion_jobs`, audit service
* [x] pgvector + pg_trgm installed, vector/FTS schema with HNSW + GIN indexes

## Phase 6 — Embeddings & Semantic Search
* [x] bge-small-en-v1.5 embeddings wired into ingestion + backfill CLI
* [x] pgvector HNSW query, Postgres FTS, Reciprocal Rank Fusion
* [x] ACL-enforced `POST /search/semantic`

## Phase 7 — Query Classification & Hybrid Retrieval
* [x] LLM route classifier (`structured/document/mixed`) with fail-open fallback
* [x] Follow-up query rewriting from chat history
* [x] OKF trigram+FTS scoring, context merger with S1…Sn refs
* [x] Retrieval orchestrator + safety net; `POST /search/okf`

## Phase 8 — LLM Answer Generation
* [x] Groq wrapper (retries, token accounting, 503 on outage)
* [x] Grounded answers with `[S#]` citations, `INSUFFICIENT_CONTEXT` fallback
* [x] Confidence formula, conversation/message/source persistence

## Phase 9 — Frontend & Analytics
* [x] Enterprise chat UI (citations, source drawer, right-side history, New chat)
* [x] Admin dashboard, user & department management, document management UI
* [x] Knowledge-base review queue (bulk approve/reject), audit log viewer
* [ ] Playwright E2E suite + Lighthouse run
* [ ] Usage analytics / AI interaction analytics

---

# 💡 Potential Use Cases

### 🏢 Human Resources
> "What is the company's leave policy?"

### 💻 IT Support
> "Who do I contact for a security incident, and how fast?"

### 📋 Project Management
> "What approvals does a high-risk production change need?"

### ⚖️ Compliance
> "What are the backup retention requirements?"

### 🎓 Employee Onboarding
> "What documents should a new employee read?"

### 🔧 Engineering
> "What is the standard procedure for deploying a service?"

Every answer is grounded in authorized enterprise documents and cites its sources.

---

# 📚 Documentation

| Document | Contents |
|---|---|
| [docs/PHASES.md](docs/PHASES.md) | **Phase-by-phase walkthrough (0–9): backend + frontend implementation of each phase** |
| [build_plan.md](build_plan.md) | Master specification (phases, acceptance criteria) |
| [docs/CHANGELOG.md](docs/CHANGELOG.md) | Detailed per-phase change log |
| [docs/AUDIT_0-5.md](docs/AUDIT_0-5.md) | Phases 0–5 audit findings & fixes |
| [docs/AS_BUILT.md](docs/AS_BUILT.md) | As-built inventory (schema, endpoints, behavior) |
| [frontend/README.md](frontend/README.md) | Frontend commands and API deviations |

---

# 🤝 Contributing

Contributions are welcome.

1. Fork the repository
2. Create a feature branch: `git checkout -b feature/new-feature`
3. Run the checks: `pytest` (backend) and `npm run typecheck && npm run lint` (frontend)
4. Commit your changes and open a Pull Request

---

# 👨‍💻 Author

## Pankaj Kumar Mahto

Computer Science & Engineering Student

Interested in: Backend Development · AI/ML · RAG Systems · Enterprise AI · Secure AI Applications

### GitHub

https://github.com/pankajkumar8709

---

# ⭐ Support

If you find this project useful, consider giving the repository a ⭐ on GitHub.

---

## 🚀 Enterprise AI Knowledge Assistant

**Building a secure foundation for intelligent enterprise knowledge.**
