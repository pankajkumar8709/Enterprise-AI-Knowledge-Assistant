# Changelog

All notable changes to the Enterprise AI Knowledge Assistant backend.

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
