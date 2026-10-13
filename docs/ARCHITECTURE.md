# Architecture & Codebase Map

> **Read this first.** This file is the orientation layer so you don't have to
> re-read the whole codebase. When you change structure, update this file in the
> same change. Last verified: 2026-10-14.

DJSCE Institutional Brain turns scattered institutional knowledge (committee
transcripts, reference documents, faculty check-ins) into decisions, tracked
commitments and cited **procedures** ("skills" in the code), fed by a continuous
capture loop (transcripts + a per-member **Institutional Assistant / PA**).
Identity: profile `institution.yaml`, Compose project `djsce-brain`, database
`djsce_brain_db`, containers `djsce_*`, Chroma collection `djsce_knowledge`.
Code still calls procedures `Skill` and staff members `Employee` (table names). See [README](../README.md) for the pitch. This file is the *engineering* map.

---

## Stack at a glance

| Layer | Tech | Where |
|---|---|---|
| Review UI | Next.js 16 (React 19) + Tailwind v4 | `frontend/src/` |
| API | FastAPI | `backend/app/api/` |
| Domain logic | Service singletons | `backend/app/services/` |
| Background jobs | Celery + Redis (worker + beat) | `backend/app/core/celery.py` |
| Relational store | Postgres (SQLite in tests) via SQLModel | `backend/app/models/structured.py` |
| Vector store | ChromaDB (fragment embeddings) | `backend/app/core/chroma_db.py` |
| Graph store | Neo4j (entity/relationship graph) | `backend/app/core/neo4j_db.py` |
| LLM | Groq (configurable) | `backend/app/services/llm_service.py` |

Ports: **API 8001**, **frontend 3000**, Postgres 5432, Neo4j 7474/7687, Chroma 8002 on host (8000 in-network), Redis 6379.

---

## Backend layout (`backend/app/`)

```
core/
  config.py        Settings (env-driven, pydantic-settings). All tunables live here.
  db.py            SQLModel engine + init_db() (registers every table) + startup_lock() (Postgres advisory
                   lock so multiple workers don't race on create_all/seeding) + get_session() dep.
  celery.py        Celery app, beat schedule, and ALL task definitions.
  chroma_db.py     Chroma connection singleton (chroma_conn).
  neo4j_db.py      Neo4j connection singleton (neo4j_conn).
  institution_config.py  Loads institution.yaml (branding, settings, help-desk categories, members).
models/
  structured.py    EVERY SQLModel table. Single source of truth for the schema.
services/          Domain logic. Each module exposes a singleton (e.g. pa_service).
api/
  router.py        Mounts all v1 routers under /api/v1.
  v1/*.py          One router per resource.
tests/             pytest suite. conftest.py mocks all external services.
```

### Services (`backend/app/services/`)

| Service | Singleton | Responsibility |
|---|---|---|
| `llm_service.py` | `llm_service` | One LLM client for all callers. `complete()` / `complete_json()` (robust JSON parsing). `is_available` gates graceful degradation. |
| `embedding.py` | `embedding_service` | Sentence-transformer embeddings. |
| `parser.py` | (funcs) | Document chunking + file parsing (txt/pdf/docx). |
| `ner_service.py` | `ner_service` | spaCy entity extraction (graph enrichment). |
| `employee_service.py` | `employee_service` | Resolve names → Employee rows; link login Users to Employees. |
| `fragment_service.py` | `fragment_service` | **Shared evidence layer.** Everything ingested — transcript utterances *and* uploaded-document chunks — becomes a Fragment (Postgres + Chroma index) with a `visibility` (`internal`/`public`). |
| `extraction_service.py` | `extraction_service` | LLM extraction: `extract_meeting()` (summary/decisions/commitments) and `extract_skill()` (procedure synthesis). |
| `transcript_service.py` | `transcript_service` | Transcript → Meeting + speaker Fragments + Commitments. |
| `commitment_service.py` | `commitment_service` | Commitment lifecycle, `needs_followup()`, `record_update()`. `VALID_STATUSES` lives here. |
| `date_parser.py` | `parse_due_date()` | Natural-language due-date parsing ("by Friday", "next week", "in 3 days", ISO). Dependency-free, deterministic. |
| `pa_service.py` | `pa_service` | Faculty Desk PA: follow-ups + end-of-day check-in; writes back Fragments + CommitmentUpdates. |
| `skill_service.py` | `skill_service` | Cluster fragments → synthesize skills → cite → lifecycle → render `SKILL.md`. |
| `freshness_service.py` | `freshness_service` | Contradiction detection → flag skills `stale` + raise ActiveInsight. |
| `audit_service.py` | `audit_service` | Append-only AuditLog for every autonomous action. |
| `institution_seed.py` | `seed_institution()` | Idempotent seeding from `institution.yaml` on startup: login Users for everyone with a password; staff also get an Employee row + reporting links (students don't). |
| `active_intel.py` | `active_intel_service` | Org-risk insights (bottlenecks) for the Active Feed. |
| `graph_service.py` | `graph_service` | Neo4j writes. Nodes `:Employee` (person), `:Project` (body: committee/cell/board/department/lab), `:Document`, `:Meeting`; edges `(Document)-[:MENTIONS]->`, `(Employee)-[:ATTENDED]->(Meeting)`, `(Meeting)-[:MENTIONS]->(Project)`. `graph_entities()` cleans NER: people need an honorific or roster match, bodies must name an institutional unit. Uniqueness constraints keep concurrent MERGEs duplicate-free. |
| `rag_service.py` | `rag_service` | Grounded Q&A via `llm_service`. `retrieve(public_only=)` filters by visibility inside the Chroma query (and re-checks results); `answer()` returns `{answer, sources}`. |
| `ticket_service.py` | `ticket_service` | Help desk: triage chain from `settings.TRIAGE_ENGINES` (default `llm,keyword`; optional `laya`, a non-generative classifier, abstains below 0.5 confidence) → keyword fallback; category/priority/`routed_to` from `institution.yaml`; staff-only AI draft (`rag_service.answer(purpose="ticket_draft")`); human reply; audited. |
| `connectors/` | registry | Source-connector framework: `base.py` + `slack/db/manual` stubs + `registry.py`. |

### API routers (`backend/app/api/v1/`) — all under `/api/v1`

| Router | Prefix | Notes |
|---|---|---|
| `auth.py` | `/auth` | register (creates a **student**)/login/me. **`require_role()`, `require_staff`, `is_staff()` live here.** |
| `ingest.py` | `/ingest` | 👥 Document upload (`visibility` and `department` form fields) → `process_document` task. |
| `insights.py` | `/insights` | 👥 Active Feed insights (list/dismiss). |
| `chat.py` | `/chat` | Grounded Q&A with `sources`; students get `public_only` retrieval. |
| `graph.py` | `/graph` | 👥 Graph data for the relationship map. |
| `transcripts.py` | `/transcripts` | 👥 Ingest transcript (202 → task) + list/get meetings. |
| `commitments.py` | `/commitments` | 👥 list / mine / patch status. |
| `pa.py` | `/pa` | 👥 followups (+reply), checkin (message/complete). |
| `skills.py` | `/skills` | 👥 list / extract🔒 / get / patch🔒 / approve🔒 / reject🔒 / file / feedback. |
| `sources.py` | `/sources` | 👥 list connectors / sync🔒. |
| `audit.py` | `/audit` | audit trail🔒. |
| `institution.py` | `/institution` | public branding (name, short code, full name) from `institution.yaml`. |
| `helpdesk.py` | `/helpdesk` | categories · tickets (create, mine) for everyone; queue / reply / retriage 👥. Non-staff only ever see their own tickets and never the AI draft. |

👥 = staff only (`require_staff`: faculty and above). 🔒 = requires `manager` role (see RBAC below).

### Data model (`backend/app/models/structured.py`)

Core tables: `User`, `Document`, `ProgressReport`, `ActiveInsight`, `Employee`,
`Meeting`, `Fragment`, `Commitment`, `CommitmentUpdate`, `CheckIn`, `Skill`,
`SkillCitation`, `AuditLog`, `Ticket`.

Conventions:
- **Lists/dicts are stored as JSON strings** (DB-agnostic: SQLite in tests, Postgres in prod). E.g. `Skill.steps`, `Meeting.participants`, `AuditLog.audit_metadata`.
- `Fragment` is the universal evidence unit; `source_type` distinguishes origin (`transcript`/`document`/`checkin`/`followup`/connector name); `visibility` decides who can retrieve it. Procedure extraction only uses `internal` fragments.
- Any new table **must** be added to the import lists in both `core/db.py:init_db()` and `tests/conftest.py` or it won't be created.

### Background jobs (`backend/app/core/celery.py`)

Tasks: `process_document`, `process_transcript`, `run_daily_active_intelligence`,
`run_daily_checkins`, `run_commitment_followups`, `run_skill_extraction`,
`run_freshness_scan`. Beat schedule is defined in the same file. Task bodies use
lazy imports so the module loads without external deps.

---

## Evaluation (`evaluation/`)

`run_eval.py` + gold sets in `evaluation/data/`. Run with `docker compose --profile eval run --rm evaluator` (backend image + optional `laya==0.3.21`, HF cache volume `hf-cache`). Writes `publication/01_ipd_report/results/` (`RESULTS.md`, `latest.json`). See `evaluation/README.md`.

---

## Frontend layout (`frontend/src/`)

> ⚠️ This is Next.js 16 / React 19 with **stricter lint rules**. See
> `frontend/AGENTS.md`. Notably `react-hooks/set-state-in-effect` forbids
> synchronous `setState` inside an effect body — fetch in promise callbacks and
> put spinner toggles in event handlers (see `app/page.tsx` for the pattern).

```
lib/api.ts                 apiFetch() — base URL, JWT header, 401→/login redirect.
lib/format.ts              formatDate()/formatDateTime() — shared date rendering.
lib/roles.ts               ROLE_LABEL (display names), isStaffRole(), useMe() (token-keyed /auth/me).
lib/useInstitution.ts      Public branding from /api/v1/institution.
components/layout/Sidebar.tsx   Role-filtered nav (NAV[].staff) + auth state via useSyncExternalStore.
components/knowledge/SourceList.tsx  Evidence excerpts behind an AI answer (public/internal badges).
components/helpdesk/TicketBadge.tsx  Ticket status/priority styling (single source).
components/graph/GraphCanvas.tsx
components/dashboard/InsightCard.tsx
app/
  page.tsx           Governance overview (staff; students are redirected to /helpdesk)
  helpdesk/          Student Help Desk: instant answers, raise ticket, my tickets
  tickets/           Staff Help Desk queue: triage, AI draft + sources, reply
  login/             Auth
  relationships/     Graph map
  meetings/          Transcript upload + meeting list
  commitments/       Action items + status updates
  assistant/         Faculty Desk PA: follow-ups + end-of-day check-in chat
  skills/            Skill review/approval + skill-file viewer
  chat/              RAG chat
  sources/           Data source upload
```

Pages talk to the API only through `apiFetch`. Design tokens (`primary`,
`danger`, `warning`, `.glass-panel`) are defined in `app/globals.css`.

---

## Cross-cutting concerns

**RBAC** — roles rank `student < employee < manager < admin` (`auth.py:_ROLE_RANK`),
shown in the UI as Student / Faculty / Committee Coordinator / System Administrator
(`frontend/src/lib/roles.ts`, display only). Gate internal data with
`Depends(require_staff)`, elevated actions with `Depends(require_role("manager"))`.
Hiding a nav item is cosmetic — the backend dependency is the control.

**Knowledge visibility** — every Fragment and its Chroma metadata carry
`visibility`. Students' chat retrieval passes `where={"visibility": "public"}` and
drops any non-public hit. Uploads default to `internal`. `get_current_user` reads the
role from the DB, so changing `User.role` takes effect without re-login.

**Department scope** — Fragments, Meetings and Chroma metadata also carry `department`
(a code from `institution.yaml`, or `all` = institution-wide); `User.department` comes from the
profile or registration. `auth.department_scope(user)` → `None` for coordinators/admins, else
`[own, "all"]` (`["all"]` with no department: fail closed). `rag_service.retrieve(departments=)`
filters inside the Chroma query (`$and` with visibility) and re-checks hits; meeting list/detail
filter the same way (other departments' meetings are 404). Ingestion takes a `department`
field (`/ingest/file` form, `/transcripts` body; `parse_department` rejects unknown codes).
Ticket drafts use the requester's department scope.

**Auth** — JWT (`sub`=email). `apiFetch` attaches the token; 401 clears it and
redirects to `/login`. Demo users are seeded from `institution.yaml`
(`admin@example.com`, coordinators, faculty, students — all `demo123`).

**Graceful LLM degradation** — services check `llm_service.is_available` and fall
back (template follow-ups, raw-fragment capture, skipped extraction) so the app
runs without a working key.

**Audit everything autonomous** — extraction, approval, skill-use, check-ins,
follow-ups, connector syncs all call `audit_service.record(...)`.

---

## Testing

`backend/tests/` — pytest. `conftest.py` sets env secrets and **mocks all
external services** (Chroma, Neo4j, embeddings, Groq) so the suite needs no
Docker. Patterns:
- Patch a service's LLM with a `MagicMock` (`is_available`, `complete_json.return_value`) at its module path, e.g. `patch("app.services.pa_service.llm_service", mock)`.
- The test DB (SQLite) is **shared across the session** — assert on your own seeded rows, not global counts.
- Promote a user to manager by setting `user.role` in `db_session`.

Run: `cd backend && .venv/Scripts/python -m pytest -q` (currently **88 passing**).

---

## Where to make common changes

| I want to… | Touch |
|---|---|
| Add a table | `models/structured.py` + both `init_db()` and `conftest.py` import lists |
| Add an endpoint | new/existing `api/v1/*.py` → register in `api/router.py` |
| Add domain logic | a `services/*.py` singleton (keep routers thin) |
| Add a scheduled job | a task + beat entry in `core/celery.py` |
| Add a tunable | `core/config.py` (env-driven) |
| Add a source | a `connectors/*.py` subclass + register in `connectors/registry.py` |
| Add a UI page | `frontend/src/app/<name>/page.tsx` + add to `Sidebar.tsx` NAV |
| Customize the institution | edit `institution.yaml` (branding/settings/help desk/people) — see [CUSTOMIZING.md](CUSTOMIZING.md) |
