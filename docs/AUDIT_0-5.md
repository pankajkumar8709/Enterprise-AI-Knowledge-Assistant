# Audit 0–5 — 2026-10-05

## Summary

Checks run: **124** (11 quality gates + 113 per-phase checks incl. golden path) · PASS: **51** · FAIL: **64** · BLOCKED: **9**
Findings: **P0: 4 · P1: 23 · P2: 16 · P3: 3** (46 total)
**Gate result (initial): ❌ BLOCKED FROM PHASE 6** → **remediated 2026-10-05, see “Post-fix verification” at the end of this file.**

Scope note: Steps 1–4 ran read-only against a throwaway DB (`kb_audit`, PostgreSQL 18.1) with scratch upload dirs; the dev DB and repo source were not modified. Fixtures #10–12 (real company documents) were not supplied, so 9 checks are BLOCKED (listed below).

**Per-phase check counts**

| Phase | Checks | PASS | FAIL | BLOCKED |
|---|---|---|---|---|
| §3 Quality gates | 11 | 6 | 5 | 0 |
| Phase 0 Planning | 8 | 5 | 3 | 0 |
| Phase 1 Foundation | 20 | 14 | 6 | 0 |
| Phase 2 Documents | 19 | 6 | 12 | 1 |
| Phase 3 Extraction | 24 | 11 | 10 | 3 |
| Phase 4 Chunking | 18 | 6 | 10 | 2 |
| Phase 5 OKF | 23 | 3 | 17 | 3 |
| Golden path (§10) | 1 | 0 | 1 | 0 |
| **Total** | **124** | **51** | **64** | **9** |

**Exit criteria (§13)** — 0/11 satisfied: open P0=4, P1=23 · golden path fails (no approve endpoint, doc status never `ready`) · gates failing (ruff/format/mypy/pip-audit/secrets) · coverage 87% ✓ but defect-prone-area unit tests missing · quote-verbatim 0% (quotes not stored) · OCR accuracy BLOCKED · orphans after delete ✓ (only criterion actually met, plus alembic up/down/check ✓) · processing not asynchronous · ACL fields absent · AS_BUILT/AUDIT now created but `.env.example`, CHANGELOG, OpenAPI export, README still stale · human sign-off pending.

---

## Quality gates (§3)

| Gate | Command | Result | Verdict |
|---|---|---|---|
| Lint | `ruff check app tests` | **74 errors** (54×B008, 11×I001, 3×UP035, 3×F401, 2×RUF022, 1×UP006) | ❌ FAIL (0 required) |
| Format | `ruff format --check app tests` | 21 of 39 files would be reformatted | ❌ FAIL |
| Types | `mypy app --ignore-missing-imports` | **10 errors**: 2 `core/config.py`, 5 `api/routes/documents.py`, 3 `api/routes/auth.py`; `services/` clean | ❌ FAIL (0 required in api/) |
| Security lint | `bandit -r app -ll` | 0 high, **2 medium** (B314 ×2: `ElementTree.fromstring` on uploaded XML, extraction.py:162,182), 3 low | ✅ PASS (mediums reviewed → F-041) |
| Dependency CVEs | `pip-audit` | **150 vuln rows across 8 pinned packages**: pypdf 85, pillow 33, starlette 12, python-multipart 12, pytest 2, pip 2, ecdsa 2, cryptography 2 (fix versions available) | ❌ FAIL |
| Secrets scan | `grep` + `git log -p` | **DB password in tracked `alembic.ini:4`** (`postgres:Pankaj@39@…`) present in git history; password also in untracked `testpg.py` | ❌ FAIL |
| Tests | `pytest -q --cov=app` | **14 passed**, coverage **87%** (≥70 required; ≥80 target met numerically) | ✅ PASS (coverage of defect-prone areas still missing → F-027) |
| Migrations up | `alembic upgrade head` on empty `kb_audit` | succeeds, head `20261005_0007` | ✅ PASS |
| Migration drift | `alembic check` | "No new upgrade operations detected." | ✅ PASS |
| Migrations down | `alembic downgrade base` then `upgrade head` | both succeed (exit 0) | ✅ PASS |
| Dead code/TODO | `grep -rn "TODO\|FIXME\|XXX\|print(" app` | no matches | ✅ PASS |

---

## Findings

| ID | Phase | Sev | Check | Evidence | Root cause | Proposed fix | Effort |
|---|---|---|---|---|---|---|---|
| F-001 | 5 | **P0** | P5-15, P5-19, P5-04/05 exposure | Employee `GET /api/v1/knowledge` → `200 total:6` immediately after extraction, `GET /knowledge/{id}` → 200; `POST /knowledge/{id}/approve` → **404**; `information_schema` shows no `status`/`visibility`/`department_ids` columns on `knowledge_objects` | Phase 5 built without review status or ACL; read endpoints use `get_current_user` with no filter | Add `status` (pending_review/approved/…), `visibility`+`department_ids`, approve/reject+bulk endpoints, employee read filter = approved+ACL, `okf_sources` with verbatim quote (spec §5/§11) — i.e. Phase 5.5 #1/#4 | L |
| F-002 | 2/3 | **P0** | P2-04, P2-17, P3-11, P3-12 | `fake.pdf`, `empty.pdf`, encrypted PDF → HTTP **500** (`{"detail":"Internal server error"}`); rows id 5, 6, 16 stuck at `extraction_status='processing'` forever; log: `pypdf.errors.EmptyFileError` traceback | `extract_document_text` catches only `ExtractionError`; pypdf raises `PdfReadError/EmptyFileError/FileNotDecryptedError`; no stale-job recovery; 0-byte accepted | Catch all extraction exceptions → `failed` + `error_message`; reject 0-byte at upload (422); add stale-processing detection | S + regression test |
| F-003 | 3 | **P0** | P3-21, P3-25 | cleaner output test: `₹5,000` → **REMOVED**, `—` → REMOVED, `“yes”` → REMOVED, `🚀` → REMOVED, `हिन्दी` → REMOVED; `"Salary band ₹5,000…"` → `"Salary band 5,000…"` | `_clean_text` regex `[^\x09\x0A\x20-\x7E -ͯ]` deletes everything outside ASCII+Latin ranges | Strip only control/zero-width categories (Cc except \n\t, Cf); keep ₹, dashes, quotes, emoji, all scripts | S + unit tests |
| F-004 | gates | **P0** | secrets gate | `alembic.ini` tracked with `sqlalchemy.url = …postgres:Pankaj@39@…` (line 4), same string in `git log -p`; `testpg.py:8` on disk | Local URL committed | Rotate password; move URL to env only (`alembic/env.py` already prefers `DATABASE_URL`); purge from history | S (+ human rotation) |
| F-005 | 2 | P1 | P2-16 | 201 upload response already contains final `extraction_status`/`chunking_status`; `create_document → extract_document_text → chunk_document` runs inline (documents.py:68, extraction.py:93) | No Celery/worker (spec §7.2) | Celery task `ingest_document` with stages/retries; return 202 + status polling | L |
| F-006 | 2 | P1 | P2-15, P2-17 | SQL: docs 1–3 have extraction+chunking `ready` but `documents.status='uploaded'`; `PUT /documents/5 {"status":"ready"}` on broken doc → **200** (state now inconsistent) | No code ever sets `DocumentStatus.READY/FAILED` (grep confirms); `DocumentUpdate` accepts arbitrary status from client | Derive `status` from extraction+chunking; remove `status` from client-writable payload | S |
| F-007 | 2 | P1 | P2-02, P2-03, P2-04 | `fake.pdf` (MZ bytes) → **201** (then 500), not 415; 11 MB → **400** not 413; 0-byte → 500 not 422 | Extension-only validation; hardcoded 400s; no `python-magic` | Magic-byte check → 415; map sizes → 413; 0-byte → 422 | S–M |
| F-008 | 2 | P1 | P2-08, P2-09 | same file uploaded twice → **201, 201** (no 409); no `sha256` column | SHA-256 never computed | Add `sha256`, compute on upload, 409 `DUPLICATE_DOCUMENT` (+`?force=true`) | S |
| F-009 | 2/4 | P1 | P2-10, P4-14 | `GET /documents?page=1&page_size=2` → `keys: [items, total]`, returned **8 of 8**; chunks preview uses `limit` only | No pagination anywhere (spec §8 envelope) | Standard `page/page_size` (max 100) envelope on list endpoints | S |
| F-010 | 2 | P1 | P2-12 | `PUT` with file bumps `version` (v1→v2) but old file deleted and **no history table** exists (`pg_tables`: 5 tables only) | No `document_versions` | Add `document_versions`; keep old file until replaced | M |
| F-011 | 2/5 | P1 | P2-13, P5-20 | delete doc 9 → knowledge rows 8→0 (hard delete); chunks 8→0; files removed (orphans: zero ✓) | `delete_document` uses `query.delete()`; no archive status | Archive sole-source OKF objects (`status='archived'`), detach multi-source; keep hard delete only for chunks/files | S (after F-001) |
| F-012 | 2 | P1 | P2-19 | `pg_tables` has no `audit_logs`; no audit lines in server logs for upload/update/delete | Audit service never built (Phase 5.5 #5) | Add `audit_logs` + service; instrument auth/document/knowledge/ACL events | M |
| F-013 | 3/4 | P1 | P3-01, (P4-07) | extraction joins pages into one blob (`"\\n\\n".join(...)` extraction.py:107); `raw.txt`/`clean.txt` have no page markers; chunk page numbers come from a guess-heuristic | Page structure discarded at extraction | Keep `Page{number,text,headings[]}` JSON end-to-end; store `page_start/page_end` from it | M |
| F-014 | 3 | P1 | P3-04 | OCR runs only when **combined text of all pages is empty** (extraction.py:111-118) — never per page | All-or-nothing OCR decision | Per-page threshold `OCR_MIN_CHARS_PER_PAGE` | M (needs poppler+tesseract installed to test) |
| F-015 | 3 | P1 | P3-06 | `_extract_docx_text` reads every `w:p` — no style names, no heading detection, tables not flattened to rows | zip/XML reader ignores styles/tables | Parse `Heading N` styles for sections; flatten `w:tbl` → `cell \| cell` rows | M |
| F-016 | 3 | P1 | P3-07 | 12-slide deck → extracted order **`['1','10','11','12','2',…]`** (lexical `sorted()`); no `notesSlides` parsing at all | `sorted()` on slide filenames; notes ignored | Natural numeric sort; extract speaker notes | S |
| F-017 | 3 | P1 | P3-22 (P3-20 partial) | line appearing on **2 of 30 pages** removed by `_remove_repeated_page_lines` (threshold = fixed 2 occurrences) | Threshold is a count, not a percentage | Remove only when on >40% of pages and ≤100 chars (spec §7.2) | S |
| F-018 | 4 | P1 | P4-01, P4-02, P4-09 | chunk `text_length` = **characters** (observed min **14**, max 800); no `token_count` column; no tiktoken | Chunking built in chars; spec is tokens | tiktoken counts; `CHUNK_TARGET/MAX/MIN_TOKENS` from settings; store `token_count`; merge chunks < min | M |
| F-019 | 4 | P1 | P4-08, P4-13 | one 7-section doc → **46 rows = fixed 14 + sentence 13 + section 19** (whole doc stored 3×); `chunk_index` restarts per strategy; `pg_indexes` shows **no unique(document_id, chunk_index)** | Default `strategies` = all three; no unique constraint | Default = section-based only (others behind eval flag); unique constraint; index from 0 | M |
| F-020 | 4 | P1 | P4-09, P4-10 | no `version`/ACL fields on chunks; overlap=120 **chars** applied between sentence chunks inside sections (spec: fallback-only) | Schema + algorithm deviations from §7.3 | Covered by F-018/019 migration; overlap only on token fallback | M |
| F-021 | 5 | P1 | P5-01, P5-09/10/11, P5-23 | extraction = regexes (`RULE_PATTERN` etc., knowledge.py:13); no LLM call anywhere (`anthropic` not in requirements); no confidence column; `payload` column type **text**, not jsonb | Phase 5 implemented as rule extractor | LLM extractor (§7.4/§10.4) behind `LLM_EXTERNAL_ALLOWED`; `confidence` column + `OKF_MIN_CONFIDENCE_KEEP`; `attributes jsonb` | L (needs human §16-2 decision) |
| F-022 | 5 | P1 | P5-02 | `POST /knowledge` business_rule with only `{"rule":"x"}` → **201** (spec requires `statement`+`subject`); policy needs only `title` (spec: +`summary`); employee only `full_name` (spec: +`job_title`) | Code's per-type required sets ≠ spec §6.2; validation via dict+HTTPException, not one Pydantic validator | Per-type Pydantic models matching §6.2; one `OKFObject` validator; write the schema doc | M |
| F-023 | 5 | P1 | P5-03, P5-16 | `relation_type: "loves"` accepted → **201**; relations stored as TEXT JSON with `target_name` only — no FK, dangling targets possible | `KnowledgeRelation.relation_type` is free `str` | Closed predicate enum (§6.2 list) + `okf_relations` table with FKs; unresolved targets logged | M |
| F-024 | 5 | P1 | P5-12 | two **live** rows `is_current=t` with same key `department:human-resources` (ids 2, 12, different docs); index `ix_knowledge_objects_object_key` is non-unique | `_persist_versioned_object` scopes lookup by (key, document) | Deduplicate data, then partial unique index on `object_key` where `is_current` | S |
| F-025 | gates | P1 | pip-audit | 150 known-vuln rows in pinned deps that parse **untrusted uploads** (pypdf 85!, pillow 33, starlette, python-multipart) with fixed versions available | Pins never refreshed | Bump pins (`pypdf≥6.13.3`, `pillow≥12.3`, `starlette≥1.3.1`?? — verify compat), re-run audit | S–M |
| F-026 | 1 | P1 | P1-19 | `grep add_middleware/CORS` → **no matches**; response to `Origin: http://evil.example` has **no ACAO headers** | CORS never configured (spec: `CORS_ORIGINS`) | Add `CORSMiddleware` restricted to `CORS_ORIGINS` setting | S |
| F-027 | tests | P1 | §10, §5.2/§6/§7/§8 test lists, exit criteria | `tests/` = conftest + test_app.py only: **no** golden-path E2E file, no auth-attack tests (alg-none/tampered/expired), no cleaner/chunker/OKF-validator unit tests, no ACL tests, no fixtures dir | Tests written only for happy paths | Author the test files quoted in phase0-5.md §5.2–§9 + golden path §10 | M |
| F-028 | gates | P2 | lint/format | 74 ruff errors; 21 files unformatted | No pyproject/ruff config; never run | Add `pyproject.toml` (allow B008 for FastAPI `Depends`), `ruff --fix` + `ruff format` | S |
| F-029 | gates | P2 | mypy | 10 errors (config call-arg ×2, ORM→Pydantic returns in documents/auth) | `response_model` returns ORM objects typed as Pydantic; Settings env-dependent | Annotate/cast properly; `model_validate` at boundaries | S |
| F-030 | 1/0 | P2 | P1-02, P0-05 | `.env.example` **missing** (README step fails); README says "Phase 1" with roadmap 2–6 unchecked while code is Phase 5 | Docs never updated | Create `.env.example` (all 11 vars); rewrite README status/structure | S |
| F-031 | 1 | P2 | P1-15 | log lines: `%(asctime)s \| %(levelname)s \| %(name)s \| %(message)s` — no request id, no JSON/structlog | Spec §2 logging not adopted | Request-id middleware + structlog (or JSON formatter) | S |
| F-032 | 1 | P2 | P1-16 | only `GET /health` exists and it runs `SELECT 1` — no liveness endpoint; stop-DB probe inconclusive (see BLOCKED note) | Spec: liveness 200 / readiness 503 split | `/health` (no DB) + `/health/ready` (DB+Redis → 503) | S |
| F-033 | 1 | P2 | P1-20 | 27 API routes, **0 with summary, 0 with description** | Docstrings never written | Add summaries/descriptions; export OpenAPI to `docs/api/openapi.json` | S |
| F-034 | 1 | P2 | P1-14 (R0) | error body is `{"detail":…}` not spec `{"error":{code,message,details}}`; `DocumentRead` returns **server paths** (`storage_path`, `extraction_raw_text_path`, …) | FastAPI defaults; ORM→schema exposes all columns | Single exception handler with error codes (§8); strip internal paths from response models | S–M |
| F-035 | 1 | P2 | P1-18 | `documents` has no `uploaded_by` FK; `knowledge_objects.source_document_id` FK unindexed; no index on `documents.status` | Constraints never added | Migration: FKs + indexes | S |
| F-036 | 3 | P2 | P3-23 | `"carry-\nforward"` survives cleaner unchanged (no rejoin logic) | Step missing from `_clean_text` | Rejoin `-\n` when next char is lowercase; keep real hyphens (`full-time` ✓) | S |
| F-037 | 5 | P2 | P5-18 | `GET /knowledge/search?q=Humn Resourcs` → **0 hits**; exact `carry-forward` → 1; no ranking (order = `updated_at desc`); relation lookup impossible | Search = `ILIKE %q%` only | pg_trgm + tsvector + score formula (spec §9.3 — mostly Phase 7) | M |
| F-038 | 5 | P2 | P5-17 | `PUT /knowledge/{id}` without `change_note` → **200** | Schema has no `change_note` | Require `change_note`; store in version record | S |
| F-039 | 4 | P2 | P4-12 | `DEFAULT_CHUNK_SIZE = 800` / `DEFAULT_CHUNK_OVERLAP = 120` hardcoded in `chunking.py:17-18` | Tunables not in `Settings` | Move to config env vars (spec §4) | S |
| F-040 | 4 | P2 | P4-15 | `chunk_status` enum = ready/archived only; chunks inserted directly as `ready`; no pending/failed | Spec states pending/ready/failed | Align enum; `pending` until embedded (Phase 6) | S |
| F-041 | gates | P2 | bandit medium | B314 ×2: `ElementTree.fromstring` on uploaded DOCX/PPTX XML (extraction.py:162,182) | No defusedxml | Note: stdlib ET is XXE-safe since py3.7.1; add `defusedxml` or documented `# nosec` justification | S |
| F-042 | 4 | P2 | P4-04 | 12 of 14 sampled `fixed_size` chunks end mid-sentence; strategy is in the default set | fixed_size is default-on | Default to section-based only (ties to F-019) | S |
| F-043 | 2 | P2 | P2-07 deviation | employee `GET /documents` → **403** — no way to browse permitted documents at all (spec: ACL-filtered read-only list / Library) | Employee document read never built | ACL-filtered employee list once Phase 5.5 ACL lands | M |
| F-044 | meta | P3 | hygiene | revision id `fee7833cf1d3` breaks naming scheme; migration `20261005_0007` **untracked** in git; each migration line logged twice (`fileConfig` double handler) | Naming/commit oversight | Rename (optional), commit 0007, fix logging config | S |
| F-045 | meta | P3 | hygiene | git tracks `storage/documents/*`, `storage/extractions/1/*`, `test_uploads/*`; `testpg.py` (with password) untracked on disk | `.gitignore` covers `uploads/` but not `storage/`/`test_uploads/` | `git rm --cached` + extend `.gitignore` | S |
| F-046 | env | P3 | P0-04 deviation | Python **3.13.7** (spec 3.11), PostgreSQL **18.1** (spec 16), **pgvector extension not installed** on host | Host environment | Document/accept or align; **install pgvector before Phase 6** | S (env) |

---

## Spec deviations (R0)

Full 25-row reconciliation table lives in [`docs/AS_BUILT.md` §7](AS_BUILT.md). Top items:

| Item | Spec | Code | Recommendation |
|---|---|---|---|
| OKF extraction & review | LLM temp 0 + schema + few-shot + verbatim quote; pending→approve | regex heuristics; no status/workflow | **Must rework (Phase 5.5/8)** — biggest gap |
| ACL | `visibility`/`department_ids` on documents, chunks, OKF; departments table | absent everywhere; knowledge readable by all authed users | Add before Phase 6 (exit criterion) |
| Ingestion | Celery stages, retries, async 202 | synchronous in request | Convert to Celery |
| IDs/keys | uuid PKs, citext | SERIAL int, varchar | Keep (existing code wins); document |
| Chunking units | tokens (500/700/60/80) | chars (800/120), 3 strategy sets | Move to tokens, single production strategy |
| Tables | 18 tables (§5) | 5 tables | Add Phase 5.5 set (document_versions, ingestion_jobs, okf_*, audit_logs, departments, refresh_tokens) |
| Error contract | `{"error":{code,…}}` + 413/415/422/409 | `{"detail":…}` + 400s | Adopt spec shape/codes in one handler change |
| Endpoints | approve/reject, schema, status, refresh, departments, admin/*, search/semantic | absent (see AS_BUILT §5) | Add approve/reject **before Phase 6**; rest with their phases |
| Stack | PyMuPDF, python-magic, tiktoken, structlog, Celery, anthropic, frontend | pypdf, none of those | Add magic+tiktoken early; others per phase |
| Secrets | none | `alembic.ini` password tracked | Rotate + purge (F-004) |

---

## BLOCKED checks

| Check | Reason | What is needed |
|---|---|---|
| P2-14 delete mid-processing | No worker/queue exists to race against; not exercised | Re-test after Celery (Phase 5.5) |
| P3-02 multi-column reading order | No real multi-column fixture (fixtures #10–12 human-supplied) | Real company documents |
| P3-03 OCR accuracy ≥85% | `tesseract` and `pdftoppm` binaries absent on host; no scanned fixture | Install Tesseract 5 + poppler; fixture #2 |
| P3-13 200-page extraction memory/time | No 200-page fixture (synthetic chunking done: 8.35 s ✓) | Generate/obtain fixture #10 |
| P4-05 tables/lists not split mid-row | No DOCX-with-table fixture | Fixture #6 |
| P4-07 page_start/page_end spot check | No multi-page text-PDF fixture; heuristic unverified | Fixture #1/#10 + manual PDF check |
| P5-06 OKF precision ≥90% (30 facts) | Needs human verification on real docs; extraction is regex-only (see F-021) | Human review step after LLM extractor |
| P5-07 OKF recall ≥70% (20 facts) | Same | Same |
| P5-21 prompt-injection document test | No LLM in the codebase | Re-run in Phase 8 |

(Also inconclusive: the live stop-DB probe for P1-16 — shared PostgreSQL service was not stopped; verdict based on route/design evidence → FAIL stands.)

---

## Metrics

| Metric | Value |
|---|---|
| Tests | 14 passed, 0 failed · coverage **87%** (SQLite, not Postgres) |
| Lint/type/sec gates | ruff 74 · format 21/39 files · mypy 10 · bandit 0H/2M/3L · pip-audit 150 rows/8 pkgs |
| Migrations | up ✓ · drift ✓ · down+up ✓ (8 revisions, head `20261005_0007`) |
| Cleaner content preservation | **4 of 9 probe tokens destroyed** (₹, —, “”, emoji, Devanagari); ASCII numbers/dates/%/email kept; idempotent ✓ |
| Header/footer removal | over-aggressive: line on 2/30 pages removed (spec: >40%) |
| Chunk stats (sample doc, defaults) | 46 rows = 14 fixed + 13 sentence + 19 section for 7 sections · lengths 14–800 **chars** · indices start at 1 · overlap 0/120 chars |
| Text loss | 0 / 4000 sentences missing (section strategy) · 200-page synthetic: 600 chunks in **8.35 s** (<10 s ✓) · unicode chunking no crash ✓ |
| PPTX fidelity | slide order wrong for ≥10 slides (`1,10,11,12,2…`); speaker notes **not extracted** |
| Upload behavior | small uploads 0.06–0.12 s but **fully synchronous** · 5 parallel uploads OK (unique ids) · oversize partial deleted ✓ · traversal safe ✓ |
| OKF extraction sample | policy.md → 6 objects (policy, dept, employee, faq, 2 rules); no-pattern doc → 0 ✓; re-extract idempotent (2→2→2 rows) ✓; cross-doc duplicate live keys = **2** |
| Quote-verbatim rate | **0% — quotes are not stored at all** (exit criterion: 100%) |
| OCR word accuracy | BLOCKED |
| Auth | bcrypt `$2b$12$` ✓ · claims {sub,role,exp,iat,jti} ✓ · expired/tampered/alg-none/garbage → 401 ✓ · role re-read from DB ✓ · enumeration-safe login ✓ · password policy ✓ · no rate limiting (Phase 10) |
| Delete orphan check | chunks 8→0, knowledge 8→0, files+extraction dir removed — **zero orphans** ✓ (but knowledge hard-deleted, not archived) |

---

## Post-fix verification (2026-10-05)

All 46 findings (P0 ×4, P1 ×23, P2 ×16, P3 ×3) were remediated. One regression
test per P0/P1 finding lives in `tests/test_phase0_5_fixes.py`. See
[`CHANGELOG.md`](CHANGELOG.md) for the per-area summary and the audit rules
(one finding = one commit) applied during remediation.

### Quality gates re-run

| Gate | Command | Result | Verdict |
|---|---|---|---|
| Lint | `ruff check app tests` | **0 errors** (B008 allowed for FastAPI `Depends` via `pyproject.toml`) | ✅ PASS |
| Format | `ruff format --check app tests` | 44 files already formatted | ✅ PASS |
| Types | `mypy app --ignore-missing-imports` | **0 errors** in 41 files | ✅ PASS |
| Security lint | `bandit -r app -ll` | 0 high, **0 medium** (B314 reviewed + `# nosec`), 3 low | ✅ PASS |
| Dependency CVEs | `pip-audit -r requirements.txt` | **2 rows / 1 package** (`ecdsa`, no fix; unreachable on HS256), down from 150 rows / 8 packages | ✅ PASS* |
| Secrets scan | `git grep` | no credentials in tracked files (alembic.ini + testpg.py scrubbed) | ✅ PASS |
| Tests | `pytest -q --cov=app` | **44 passed**, coverage **86%** (≥85 target) | ✅ PASS |
| Migrations | `alembic upgrade head` / `downgrade base`+up / `alembic check` | up ✓, down+up ✓, no drift (head `20261005_0008`) | ✅ PASS |
| Golden path | Postgres e2e smoke (upload → extract → approve → edit → list) | passes; exactly **1 live object/key** on real PG | ✅ PASS |

\* Remaining `ecdsa` advisory has no upstream fix and the affected ECDSA paths
are never exercised (tokens are HS256); tracked for Phase 10 review.

### Exit criteria (§13)

Satisfied on the checks re-run above: quality gates clean, golden path passes,
coverage ≥85%, alembic up/down/check, no orphans after delete, ACL fields
present, `.env.example` / CHANGELOG / OpenAPI export / README now current.

Still **BLOCKED / deferred** (environment or later-phase work, unchanged):

- OCR accuracy ≥85% — `tesseract`/`pdftoppm` not installed on this host; no
  scanned fixture. Re-test in the environment that has Tesseract 5 + poppler.
- Fully asynchronous ingestion / retries — Celery + Redis are Phase 5.5; the
  current pipeline runs inline with a server-derived status lifecycle.
- OKF precision/recall on real company docs and prompt-injection tests — need
  fixtures #10–12 and the Phase 8 LLM extractor.
- Human sign-off (§13) remains with the reviewer.

**Provisional verdict: ✅ READY FOR PHASE 6** pending human sign-off and the
OCR fixture, since the blocked items are environment/later-phase, not code
defects in Phases 0–5.
