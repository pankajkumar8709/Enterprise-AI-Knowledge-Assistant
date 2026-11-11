# Presentation Script  
## Enterprise AI Knowledge Assistant  
**Minor / Learning Project — School of Engineering and Technology, GIET University**

**Team:** Pankaj Kumar Mahto · Mirtunjay Kumar Verma · Soumya Ranjan Rout  
**Guide:** Mr. Jagadish Sahoo, Assistant Professor, Dept. of CSE  

**Suggested total time:** 10–12 minutes + Q&A  
**Tone:** Clear, confident, technical but understandable to faculty from CSE

---

### Before you start
- Open the slides and, if possible, have the app ready (login page or a completed Q&A with citations).
- Decide who speaks which section (suggested split at the end).
- Keep answers short in Q&A; offer to show the live system if asked.

---

## SLIDE 1 — Title  
**(~20 seconds)**

> Good morning / Good afternoon, everyone.  
>  
> We are Pankaj Kumar Mahto, Mirtunjay Kumar Verma, and Soumya Ranjan Rout from the Department of Computer Science and Engineering.  
>  
> Under the guidance of Mr. Jagadish Sahoo, we present our minor project: **Enterprise AI Knowledge Assistant** — a secure, full-stack system that lets employees ask questions in natural language and receive answers grounded in company documents, with source citations and access control.

---

## SLIDE 2 — Outlines  
**(~15 seconds)**

> Our presentation has five parts:  
> one, project introduction and objectives;  
> two, system design and architecture;  
> three, functional prototype and demonstration;  
> four, testing, validation, and feature completeness;  
> and five, documentation, results, and future scope.

---

## SLIDE 3 — Project Introduction & Problem Statement  
**(~1 minute)**

> **What is this project?**  
> It is a full-stack platform where an organisation can manage its knowledge and employees can ask questions in plain language. Every answer is grounded in the company’s own documents, cites its sources, and the system says so honestly when it does not know.  
>  
> **Who is it for?**  
> Employees use chat and the document library to find approved knowledge. Admins upload documents, review extracted knowledge, and manage users.  
>  
> **Why does it matter?**  
> In most organisations, information is scattered across policies, reports, HR files, and technical docs. Keyword search is slow and incomplete. Generic chatbots are not tied to internal documents and can hallucinate. We need grounded answers that also respect **who is allowed to see what**.

---

## SLIDE 4 — Objectives & Existing System  
**(~45 seconds)**

> Our objectives were to:  
> - centralise enterprise knowledge on one secure platform;  
> - automatically ingest PDF, DOCX, PPTX, TXT, and Markdown;  
> - retrieve with hybrid vector and full-text search;  
> - generate grounded answers with **[S#]** source citations;  
> - enforce role and department access on every query; and  
> - ship a React chat UI and admin console.  
>  
> Existing approaches fall short: manual or keyword search does not scale; generic LLMs are not grounded and may invent facts; many basic RAG demos omit access control and proper citations. That gap is what we set out to close.

---

## SLIDE 5 — Proposed System & Key Advantages  
**(~45 seconds)**

> Our proposed system is a **secure hybrid-RAG assistant**: upload documents, ask questions, get cited answers limited to what each user may access.  
>  
> Key capabilities:  
> - **Ingestion** of PDF, DOCX, PPTX, TXT, and MD, with OCR fallback for scanned pages;  
> - **Hybrid retrieval** using pgvector and full-text search, fused with Reciprocal Rank Fusion;  
> - **Grounded answers** from the Groq LLM with **[S#]** citations and a confidence score;  
> - **Access control** — RBAC plus department ACL enforced inside SQL, not only in the UI;  
> - **Knowledge review** — structured OKF facts that admins can approve or reject; and  
> - a **React web app** with chat, admin console, and document library.  
>  
> Scope covers the full pipeline: processing, semantic and keyword search, knowledge extraction, access control, and contextual answers.

---

## SLIDE 6 — System Architecture  
**(~1 minute)**

> Architecturally, the browser runs a React SPA — chat, admin console, and library — talking to the backend over HTTPS with JWT.  
>  
> The **FastAPI** backend handles authentication, RBAC, ACL, and audit logging.  
>  
> The **ingestion pipeline** validates uploads, extracts and cleans text, chunks by section, and embeds with a 384-dimension model.  
>  
> The **retrieval engine** rewrites follow-up questions, classifies the need, runs vector and full-text search, fuses ranks with RRF, and searches approved knowledge objects.  
>  
> **Answer generation** merges context, calls Groq, attaches **[S#]** citations and confidence, and saves the conversation.  
>  
> All of this sits on **PostgreSQL** with pgvector and full-text support. The browser never talks to the database or holds LLM keys — that trust boundary is intentional.

---

## SLIDE 7 — ER Diagram & User Workflow  
**(~40 seconds)**

> *[Point to ER diagram]*  
> The data model links users and departments to documents, chunks, and knowledge objects. Conversations own messages, and messages retain source records so citations stay inspectable even if evidence is later archived.  
>  
> Document visibility is stored as attributes — including department lists as JSON — and applied in retrieval SQL, not as a loose UI filter.  
>  
> *[Point to user workflow]*  
> From the user’s view the flow is simple: log in, ask a question or browse the library, receive a grounded answer with sources, and inspect any citation. Admins additionally upload documents and review knowledge.

---

## SLIDE 8 — Technology Stack & Methodology  
**(~50 seconds)**

> On the backend we use Python and FastAPI, PostgreSQL 18 with pgvector, SQLAlchemy 2 and Alembic, JWT with bcrypt, the **bge-small-en-v1.5** embedding model, and the **Groq** SDK for classification, rewriting, and answers.  
>  
> The frontend is React 18, TypeScript, Vite, Tailwind, and TanStack Query. Testing is primarily Pytest.  
>  
> Methodology in six steps:  
> 1. upload and validate;  
> 2. extract and clean, with OCR when needed;  
> 3. chunk and embed;  
> 4. hybrid retrieve — vector, full-text, RRF, and OKF;  
> 5. generate a grounded answer with Groq;  
> 6. attach citations and confidence, and save the chat.

---

## SLIDE 9 — Functional Prototype & Live Demonstration  
**(~1–2 minutes — expand if you show the live app)**

> The working prototype supports the full path:  
> **login → upload document → ask a question → view [S#] sources.**  
>  
> Locally, the API runs with Uvicorn on port 8000 and the UI with Vite on port 5173.  
>  
> *[If demo is available:]*  
> I will briefly show: logging in, the admin document list and upload, asking a policy question in chat, and opening a citation to the supporting passage.  
> *[If no live demo:]*  
> Our report and screenshots document login, dashboard, upload and processing status, knowledge review, cited answers, source inspection, and the employee library.

---

## SLIDE 10 — Functionality & Feature Completeness  
**(~45 seconds)**

> **Completed:** JWT auth with refresh rotation and roles; ingestion for five formats with OCR fallback; chunking and embeddings; hybrid retrieval; OKF review workflow; grounded Groq answers with citations; and the React chat, admin, and library UIs.  
>  
> **Still pending or partial:** XLSX processing, LLM-based OKF extraction — we currently use regex heuristics — Playwright end-to-end tests, and usage analytics.  
>  
> **Contributions:** Pankaj — frontend and LLM integration on the backend; Mirtunjay — backend services and APIs; Soumya — schema design and database tables.

---

## SLIDE 11 — Testing & Validation  
**(~50 seconds)**

> We validated with **97 automated Pytest tests**, including a regression test for each audit P0/P1 finding. The frontend type-checks, lints, and production-builds cleanly. APIs were exercised through Swagger.  
>  
> Sample cases: unsupported upload returns **415**; duplicate content returns **409**; wrong password and unknown email both return the same **401** — no user enumeration; restricted documents are not retrieved for unauthorised employees because ACL runs in SQL; questions with no evidence return an honest insufficient-context fallback; and if Groq is down, the API returns **503** rather than inventing an answer.  
>  
> We also care about latency, retrieval quality, and API response time in evaluation.

---

## SLIDE 12 — Documentation & User Manual  
**(~30 seconds)**

> Setup is documented: clone, virtualenv, dependencies, PostgreSQL with extensions, and Alembic migrations. Configuration uses `.env` for database URL, JWT secret, and Groq API key — secrets are not committed.  
>  
> Employees log in, ask questions, and open sources; admins upload documents, review knowledge, and manage users. Full API docs are available at `/docs` and `/redoc`, with additional design notes in the repository.

---

## SLIDE 13 — Results, Conclusion & Future Scope  
**(~45 seconds)**

> **Results in brief:** 97 backend tests passing, phases 0 through 9 completed, five document formats supported.  
>  
> **Limitations** we acknowledge: no XLSX yet, heuristic OKF extraction, and no full browser E2E suite or analytics dashboard.  
>  
> **Conclusion:** we delivered a secure, full-stack RAG assistant that provides **cited, access-controlled** answers over enterprise documents — not just a chatbot demo.  
>  
> **Future work:** XLSX support, LLM-based knowledge extraction, Playwright and Lighthouse, and a usage analytics dashboard.

---

## SLIDE 14 — References  
**(~15 seconds)**

> Our work builds on established research and tools: Lewis et al. on Retrieval-Augmented Generation; Cormack et al. on Reciprocal Rank Fusion; HNSW for vector search; and the official documentation for FastAPI, pgvector, Groq, and the BGE embedding model.

---

## SLIDE 15 — Q&A  
**(~10 seconds + discussion)**

> Thank you for your attention. We are happy to take questions — or to walk through the live system if you would like.

---

# Suggested speaker split

| Section | Suggested owner |
|--------|------------------|
| Title, outlines, introduction, problem, objectives | Pankaj |
| Proposed system, architecture, ER, tech stack | Mirtunjay |
| Demo / prototype, features, contributions | Pankaj + Soumya |
| Testing, documentation, results, future scope, Q&A | Team (Mirtunjay opens testing; all handle Q&A) |

---

# Likely Q&A — short answers

**Q. Why Groq and not a local LLM?**  
> Groq gives low-latency hosted inference for classification, rewriting, and answers. The design keeps the provider configurable; embeddings already run locally with BGE.

**Q. How do you stop users from seeing other departments’ documents?**  
> Visibility and department lists are stored on documents and enforced in SQL during retrieval — before context is sent to the LLM — so the model never sees unauthorised passages.

**Q. What if the model still hallucinates?**  
> We only generate when retrieval found evidence; otherwise we return an explicit insufficient-context response. Answers include **[S#]** citations so users can verify the passage. We do not treat chat output as approved knowledge.

**Q. Why hybrid search, not vector only?**  
> Semantic search handles paraphrases; full-text catches exact policy IDs and phrases. RRF merges the two ranked lists without forcing scores onto one scale.

**Q. Is this production-ready?**  
> It is a complete minor-project prototype with automated tests and a clear security model. Production would still need hardening: durable job queues, shared storage, load tests, and formal security review — which we list under future scope and limitations.

**Q. What did each member do?**  
> Pankaj — frontend and backend LLM integration; Mirtunjay — backend core; Soumya — database schema and tables. We collaborated on integration and testing.

---

# Delivery tips
- Speak to the audience, not the screen; glance at bullets only.  
- On architecture and ER slides, **point** while you explain — it holds attention.  
- If the live demo fails, go straight to screenshots and the test table; do not spend time debugging on stage.  
- In Q&A, if you do not know, say so and offer to follow up — better than guessing.  
- Stay within time: aim to reach Q&A by minute 11.
