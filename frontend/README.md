# Knowledge Assistant — frontend (Phase 9)

React 18 + TypeScript (strict) + Vite + Tailwind. Implements the Phase 9 spec in
[`build_plan.md`](../build_plan.md) §13: the admin console (§12.1), the employee chat
experience (§12.2) and the edge-case behaviour (§12.3).

## Commands

```bash
npm ci                       # install (Node 20+)
npm run dev                  # dev server on :5173, proxies /api → http://localhost:8000
npm run typecheck            # tsc --noEmit (0 errors, no `any`)
npm run lint                 # ESLint (flat config, type-aware)
npm run build                # typecheck + production build to dist/
npm run preview              # serve dist/ locally
```

The dev server proxies `/api` to `http://localhost:8000`, so no CORS setup is needed
locally. In production set `VITE_API_URL` (defaults to the same-origin `/api/v1`) — see
[`.env.example`](.env.example).

## Route map (§13.3)

| Route | Access | Page |
|---|---|---|
| `/login`, `/signup` | public (redirect to home when signed in) | [Login.tsx](src/pages/Login.tsx), [Signup.tsx](src/pages/Signup.tsx) |
| `/app/chat`, `/app/chat/:conversationId` | any signed-in user | [Chat.tsx](src/pages/app/Chat.tsx) |
| `/app/documents` | any signed-in user | [Library.tsx](src/pages/app/Library.tsx) |
| `/admin/dashboard` · `/admin/documents` · `/admin/documents/:id` · `/admin/knowledge` · `/admin/knowledge/review` · `/admin/knowledge/:id` · `/admin/users` · `/admin/audit-logs` | `RequireRole role="admin"` (employees get an explicit 403 page) | [pages/admin](src/pages/admin) |
| `/` | redirect by role (admin → dashboard, employee → chat) | [HomeRedirect.tsx](src/pages/HomeRedirect.tsx) |
| `/dev/ui` | public | component gallery ([DevUi.tsx](src/pages/DevUi.tsx)) |
| `*` | — | [NotFound.tsx](src/pages/NotFound.tsx) |

## Architecture

- **Design tokens** are fixed in [`tailwind.config.ts`](tailwind.config.ts) +
  [`src/index.css`](src/index.css): Inter/JetBrains Mono via `@fontsource` (no CDN),
  indigo-600 primary, slate neutrals, `rounded-2xl` cards / `rounded-xl` controls,
  `shadow-sm|md|xl`, the §13.1 type scale, a global visible focus ring and
  `prefers-reduced-motion` support.
- **Primitives** live in `src/components/ui/` (Card, Badge, Button, Input, Textarea,
  Select, Modal, Drawer, Tabs, Table, Skeleton, Spinner, Toast, EmptyState, ErrorState,
  ProgressSteps, StatCard, Tooltip, ConfirmDialog, Avatar). Modal/Drawer trap focus and
  restore it on close.
- **Server state** is TanStack Query only (`staleTime` 30 s). Mutations invalidate the
  affected key prefixes; failures surface `ApiError.error.message` as a toast.
- **Forms** use react-hook-form + zod with inline errors; every form is `noValidate` so
  the styled zod messages are used instead of the browser's native bubbles.
- **Auth** is a Zustand store persisted to `localStorage` under `kb-auth`
  ([authStore.ts](src/store/authStore.ts)). The axios client
  ([lib/api.ts](src/lib/api.ts)) attaches the bearer token and refreshes **once** on a
  401 (single-flight shared across concurrent requests); if refresh fails the session is
  cleared and the browser lands on `/login?expired=1` with a toast.
- **Lists and tables** always render a Skeleton (loading), an EmptyState (with a next
  action) and an ErrorState (with Retry).
- **Documents polling**: each row that is `processing` polls
  `GET /documents/{id}/status` every 3 s and refreshes the list when it settles.

## Deviations from the spec's DTO sketch

The plan's §13.4 type sketch assumes UUID ids and several renamed fields. The shipped
backend (Phases 0–8) uses **integer primary keys** and the names below, so the frontend
follows the running API — otherwise no §12 flow could work end to end. The error
envelope `{"error":{"code","message","details"}}` **does** match the spec (verified live).

| Plan §13.4 / §8 | Actually implemented | Frontend handling |
|---|---|---|
| IDs are UUID strings | `int` primary keys everywhere | types use `number` |
| `DocumentDto.original_filename`, `file_ext`, `page_count`, `ocr_used`, `current_version`, `stage`, `error_message`, `okf_count` | `DocumentRead` has `source_name`, `content_type`, `extraction_ocr_used`, `version`; no page/okf counts or stage | file extension derived from `source_name`; stage comes from `GET /documents/{id}/status`; the table shows chunks instead of facts |
| `GET /documents` filters `status,q,visibility,department_id` | only `page`,`page_size` | the page loads the newest 100 rows and filters/paginates client-side, showing a note when the corpus is truncated |
| `GET /documents/{id}/text` → `pages[]` | `GET /documents/{id}/extracted-text` → `raw_text`/`clean_text` | "Extracted text" tab with a Clean/Raw toggle |
| `GET /documents/{id}/chunks` | `GET /documents/{id}/chunks/preview` (paginated) | `ChunkTable` paginates with `page`/`page_size` |
| `OkfObjectDto.type/canonical_key/attributes/version/valid_from/valid_to/sources[]` | `object_type/object_key/payload/object_version`; a single `source_excerpt` + `source_document_id`; `relations[relation_type,target_type,target_name,evidence]` | mapped in the knowledge components; relations render as `predicate → target` chips |
| `GET /knowledge/schema` drives the manual form | endpoint does not exist | local `OKF_FIELD_SPECS` table (spec §6.2) drives [OkfForm](src/components/knowledge/OkfForm.tsx) |
| `GET /knowledge` filters `type,status,q` | `object_type`, `document_id`, `include_history` (search via `/knowledge/search`) | type filter is server-side; status and free-text filtering are client-side |
| `visibility=all` as a filter sentinel | collides with `Visibility.all` | `''` is the "no filter" sentinel in every filter select |
| `POST /documents` title optional | `title` is a required form field | upload modal pre-fills the title from the filename |
| `GET /chat/conversations` paginated | returns a plain array | `ConversationList` takes an array |
| `GET /chat/conversations/{id}` returns messages **with** sources | messages only (`id, role, content, created_at`) | history answers render as plain Markdown with `[S#]` markers stripped; badges/citations appear for turns sent in the current session |
| `POST /search/semantic`, `POST /search/okf` | implemented | no §13.7 page consumes them (chat retrieves server-side), so the UI does not call them |

## What is and isn't verified

Static gates:

- `tsc --noEmit` → 0 errors; ESLint → 0 problems; `npm run build` → success.
- No `any` anywhere in `src` (`grep` + `@typescript-eslint/no-explicit-any: error`).

Live pass against `uvicorn` on :8000 + PostgreSQL 18, signed in as a throwaway employee
(created through the signup page and deleted afterwards):

- `/dev/ui`, `/login`, `/signup`, 404 render correctly, no console errors.
- Login validation shows inline zod errors (browser bubbles suppressed); a rejected login
  renders the API message "Invalid credentials" — proving Vite proxy → FastAPI →
  error-envelope → client mapping.
- Signup → auto-login → `/app/chat`; suggestion card → optimistic user bubble +
  "Searching company knowledge…" skeleton → answer; the unanswerable card renders when
  retrieval finds nothing; a client timeout renders the danger card with a working Retry.
- Conversation sidebar: auto-title from the first message, confirm-delete, drawer on
  narrow screens.
- Library lists exactly the documents the ACL returns; employee → `/admin/*` shows the 403
  page.
- Every admin page rendered with real data: dashboard stats, documents table, document
  detail (Overview / Extracted text / Chunks / Knowledge), knowledge list, review queue,
  knowledge detail (attributes, relations, provenance, versions), users & departments,
  audit logs.
- Responsive at 375 / 768 / 1280 px (sidebar → drawer, icon rail, composer clears the last
  message at the bottom of the scroll).

Not yet covered:

- The Playwright suite and Lighthouse run required by the §14 acceptance criteria
  (accessibility measures implemented: focus rings, `aria-label` on icon buttons, focus
  traps in Modal/Drawer, semantic tables, `aria-live` toasts, reduced-motion support).
- **Grounded answers with citations**: the dev database has 0 `document_chunks` rows and 0
  approved knowledge objects, so retrieval returns nothing and every answer is the
  unanswerable fallback. The citation chips, sources list and source drawer are therefore
  unexercised against live data.
- The main bundle is 761 kB (not code-split).
