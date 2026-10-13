# Architecture & Codebase Map

> **Read this first.** This file is the orientation layer so you don't have to
> re-read the whole codebase. When you change structure, update this file in the
> same change. Last verified: 2026-10-13.

DJSCE Institutional Brain turns scattered institutional knowledge (committee
transcripts, reference documents, faculty check-ins) into decisions, tracked
commitments and cited **procedures** ("skills" in the code), fed by a continuous
capture loop (transcripts + a per-member **Institutional Assistant / PA**).
Internal identifiers keep the original Company-Brain names (`company.yaml`,
`company_brain_db`, `cb_*` containers, `company_brain_chunks` collection) —
renaming them would orphan existing Docker volumes. See [README](../README.md) for the pitch. This file is the *engineering* map.

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
  db.py            SQLModel engine + init_db() (registers every table) + get_session() dep.
  celery.py        Celery app, beat schedule, and ALL task definitions.
  chroma_db.py     Chroma connection singleton (chroma_conn).
  neo4j_db.py      Neo4j connection singleton (neo4j_conn).
  company_config.py  Loads company.yaml (per-company profile: branding, settings, org).
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
| `fragment_service.py` | `fragment_service` | **Shared evidence layer.** Everything ingested becomes a Fragment (Postgres + Chroma index). |
| `extraction_service.py` | `extraction_service` | LLM extraction: `extract_meeting()` (summary/decisions/commitments) and `extract_skill()` (procedure synthesis). |
| `transcript_service.py` | `transcript_service` | Transcript → Meeting + speaker Fragments + Commitments. |
| `commitment_service.py` | `commitment_service` | Commitment lifecycle, `needs_followup()`, `record_update()`. `VALID_STATUSES` lives here. |
| `date_parser.py` | `parse_due_date()` | Natural-language due-date parsing ("by Friday", "next week", "in 3 days", ISO). Dependency-free, deterministic. |
| `pa_service.py` | `pa_service` | Company PA: follow-ups + end-of-day check-in; writes back Fragments + CommitmentUpdates. |
| `skill_service.py` | `skill_service` | Cluster fragments → synthesize skills → cite → lifecycle → render `SKILL.md`. |
| `freshness_service.py` | `freshness_service` | Contradiction detection → flag skills `stale` + raise ActiveInsight. |
| `audit_service.py` | `audit_service` | Append-only AuditLog for every autonomous action. |
| `company_seed.py` | `seed_company()` | Idempotent org-structure seeding (Users+Employees+managers) from `company.yaml`, run on startup. |
| `active_intel.py` | `active_intel_service` | Org-risk insights (bottlenecks) for the Active Feed. |
| `graph_service.py` | `graph_service` | Neo4j upserts (employees/projects/edges). |
| `rag_service.py` | `rag_service` | RAG chat over fragments/graph (reviewer aid). |
| `connectors/` | registry | Source-connector framework: `base.py` + `slack/db/manual` stubs + `registry.py`. |

### API routers (`backend/app/api/v1/`) — all under `/api/v1`

| Router | Prefix | Notes |
|---|---|---|
| `auth.py` | `/auth` | register/login/me. **`require_role()` RBAC helper lives here.** |
| `ingest.py` | `/ingest` | Generic document upload → `process_document` task. |
| `insights.py` | `/insights` | Active Feed insights (list/dismiss). |
| `chat.py` | `/chat` | RAG chat. |
| `graph.py` | `/graph` | Graph data for the relationship map. |
| `transcripts.py` | `/transcripts` | Ingest transcript (202 → task) + list/get meetings. |
| `commitments.py` | `/commitments` | list / mine / patch status. |
| `pa.py` | `/pa` | followups (+reply), checkin (message/complete). |
| `skills.py` | `/skills` | list / extract🔒 / get / patch🔒 / approve🔒 / reject🔒 / file / feedback. |
| `sources.py` | `/sources` | list connectors / sync🔒. |
| `audit.py` | `/audit` | audit trail🔒. |
| `company.py` | `/company` | public branding (name + logo) from `company.yaml`. |

🔒 = requires `manager` role (see RBAC below).

### Data model (`backend/app/models/structured.py`)

Core tables: `User`, `Document`, `ProgressReport`, `ActiveInsight`, `Employee`,
`Meeting`, `Fragment`, `Commitment`, `CommitmentUpdate`, `CheckIn`, `Skill`,
`SkillCitation`, `AuditLog`.

Conventions:
- **Lists/dicts are stored as JSON strings** (DB-agnostic: SQLite in tests, Postgres in prod). E.g. `Skill.steps`, `Meeting.participants`, `AuditLog.audit_metadata`.
- `Fragment` is the universal evidence unit; `source_type` distinguishes origin (`transcript`/`slack`/`checkin`/`followup`/`manual`/…).
- Any new table **must** be added to the import lists in both `core/db.py:init_db()` and `tests/conftest.py` or it won't be created.

### Background jobs (`backend/app/core/celery.py`)

Tasks: `process_document`, `process_transcript`, `run_daily_active_intelligence`,
`run_daily_checkins`, `run_commitment_followups`, `run_skill_extraction`,
`run_freshness_scan`. Beat schedule is defined in the same file. Task bodies use
lazy imports so the module loads without external deps.

---

## Frontend layout (`frontend/src/`)

> ⚠️ This is Next.js 16 / React 19 with **stricter lint rules**. See
> `frontend/AGENTS.md`. Notably `react-hooks/set-state-in-effect` forbids
> synchronous `setState` inside an effect body — fetch in promise callbacks and
> put spinner toggles in event handlers (see `app/page.tsx` for the pattern).

```
lib/api.ts                 apiFetch() — base URL, JWT header, 401→/login redirect.
lib/format.ts              formatDate()/formatDateTime() — shared date rendering.
components/layout/Sidebar.tsx   Nav (NAV array) + auth state via useSyncExternalStore.
components/graph/GraphCanvas.tsx
components/dashboard/InsightCard.tsx
app/
  page.tsx           Active Feed (insights)
  login/             Auth
  relationships/     Graph map
  meetings/          Transcript upload + meeting list
  commitments/       Action items + status updates
  assistant/         Company PA: follow-ups + end-of-day check-in chat
  skills/            Skill review/approval + skill-file viewer
  chat/              RAG chat
  sources/           Data source upload
```

Pages talk to the API only through `apiFetch`. Design tokens (`primary`,
`danger`, `warning`, `.glass-panel`) are defined in `app/globals.css`.

---

## Cross-cutting concerns

**RBAC** — roles rank `employee < manager < admin` (`auth.py:_ROLE_RANK`). Gate
an endpoint with `Depends(require_role("manager"))`. `get_current_user` reads the
role from the DB, so changing `User.role` takes effect without re-login.

**Auth** — JWT (`sub`=email). `apiFetch` attaches the token; 401 clears it and
redirects to `/login`. Demo user seeded on first boot: `demo@example.com` /
`demo123` (admin).

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
| Customize for a company | edit `company.yaml` (branding/settings/org) — see [CUSTOMIZING.md](CUSTOMIZING.md) |
