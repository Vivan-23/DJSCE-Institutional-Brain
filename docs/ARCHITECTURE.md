# Architecture & Codebase Map

> **Read this first.** This file is the orientation layer so you don't have to
> re-read the whole codebase. When you change structure, update this file in the
> same change. Last verified: 2026-10-28.

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
  db.py            SQLModel engine + init_db() (runs Alembic `upgrade head`; stamps pre-migration DBs) + startup_lock() (Postgres advisory
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
| `notice_service.py` | `notice_service` | Audience filters (roles, departments, years, semesters, divisions; AND across kinds, OR within). Faculty forced to own department. Recipients resolved and stored at send time (`NoticeRecipient`); expiry hides; audited. |
| `user_service.py` | `user_service` | User management rules: validation, cohort check (semester 2y-1/2y), no self-demotion, last active admin kept, Employee profile for staff, audited. |
| `analytics_service.py` | `analytics_service` | Computed on read from Commitment/Meeting, Ticket, QueryLog, Fragment, Skill. Questions are grouped by normalized text; topic = offline keyword triage category. |
| `schedule_service.py` | `schedule_service` | Teaching schedule: published `TimetableEntry` rows mapped to a faculty member, expanded per date on read (nothing materialized), adjusted by `ScheduleException` (cancelled / modified / holiday / extra). Local dates in `settings.INSTITUTION_TIMEZONE`. `weekly_load()` = teaching hours. |
| `timetable_extract.py` | `extract()` | File → transcribed boxes `{day,start,end,text}` + header + legend, no interpretation. .docx/.xlsx/.csv grids read directly (position-based box ids; identical text below = merged); photos/PDF (pymupdf renders page 1) transcribed twice by `settings.TIMETABLE_VISION_MODEL`, disagreeing boxes marked `check`. |
| `timetable_parser.py` | (funcs) | Deterministic cell grammar → `Slot`s (subject, batch, faculty list, room, kind), header → class_key, 12h→24h. Unreadable text kept with `unparsed`. |
| `timetable_service.py` | `timetable_service` | Upload (SHA-256 dedupe) → extraction draft → review flags (blocking vs warning) → diff vs published → publish (supersedes that class only, carries date exceptions, notifies, audits). Initials resolve only via `FacultyAlias`; `suggestions()` from legend/initials are hints. |
| `calendar_service.py` | `calendar_service` | Merges `academic_calendar:` (institution.yaml) with commitment due dates; `post_reminders()` writes `deadline` ActiveInsights (idempotent) for items due within 3 days. `sync_fragments()` (on startup) indexes each date as a `source_type="calendar"` Fragment (public unless `audience: staff`; plus one public overview) so the assistant can answer "when is TT1?"; idempotent, drops dates removed from the yaml. |
| `minutes_service.py` | `minutes_service` | Formal draft minutes from a stored meeting (attendees, summary, `Meeting.decisions`, commitments with owner/due/status) → DOCX (python-docx) or PDF (reportlab). No LLM call at export time. |
| `procedure_service.py` | `procedure_service` | SOP governance: approve (freeze `SkillVersion`, owner office, review date, publish), `publish()` indexes approved procedures as `source_type="procedure"` fragments (`Fragment.skill_id`; staff full text, students only the summary), revisions, reject/retire, feedback flagging, use counts, DOCX/PDF export + handbook. |
| `ticket_service.py` | `ticket_service` | Help desk: triage chain from `settings.TRIAGE_ENGINES` (default `llm,keyword`; optional `laya`, a non-generative classifier, abstains below 0.5 confidence) → keyword fallback; category/priority/`routed_to` from `institution.yaml`; staff-only AI draft (`rag_service.answer(purpose="ticket_draft")`); human reply; audited. |
| `connectors/` | registry | Source-connector framework: `base.py` + `slack/db/manual` stubs + `registry.py`. |

### API routers (`backend/app/api/v1/`) — all under `/api/v1`

| Router | Prefix | Notes |
|---|---|---|
| `assistant.py` | `/assistant` | 🔑 One box: `message` routes to check-in updates / RAG answers / own schedule (`assistant_service`); `undo` reverts an assistant task change (owner). |
| `auth.py` | `/auth` | register (creates a **student**)/login/me/`change-password`. **`require_role()`, `require_staff`, `is_staff()` live here.** `User.must_change_password` is set whenever an admin issues a generated password (create, CSV import, reset); the Sidebar sends such users to `/password` until they choose their own. |
| `ingest.py` | `/ingest` | 👥 Document upload (`visibility` and `department` form fields) → `process_document` task; `GET /documents` lists uploaded files (grouped `source_type="document"` fragments, `department_scope`-filtered). |
| `insights.py` | `/insights` | 👥 Active Feed insights (list/dismiss). |
| `chat.py` | `/chat` | Grounded Q&A with `sources`; students get `public_only` retrieval. |
| `graph.py` | `/graph` | 👥 `/data?limit=` (whole graph, bounded, `truncated` flag), `/neighbors/{id}?depth=` (a node's neighbourhood, for large graphs), `/stats`. Department-scoped: Document/Meeting nodes carry `department`. |
| `transcripts.py` | `/transcripts` | 👥 Ingest transcript (202 → task) + list/get meetings. | `GET /{id}/minutes?format=docx|pdf` (Coordinator+) exports formal draft minutes.
| `commitments.py` | `/commitments` | 👥 Tasks. `GET` (dept-scoped), `/mine`, `/my-work` (summary + own tasks; coordinators also get `awaiting_my_confirmation`), `/team` and `/assignable` (coordinator), `GET /{id}` (timeline + most-likely source line), `POST /{id}/progress` and `/done` (owner only), `/confirm` and `/send-back` (coordinator), `POST` create (coordinator), `PATCH` (owner: own statuses; coordinator: any status, due date, reassign). |
| `pa.py` | `/pa` | 👥 followups (+reply), checkin (message/complete). |
| `skills.py` | `/skills` | Procedures (SOPs). Staff (dept-scoped): list/search, detail (+citations, feedback), `/versions`, `/file` (SKILL.md), `/export?format=`, `/handbook?format=`. Students: `/student` (approved, student-facing summaries). Coordinator: `POST` (write by hand), `/extract`, `PATCH` (content → new pending version; settings keep approval), `/approve`, `/reject` (reason required), `/retire`. `/feedback` (3 "wrong" → needs review). |
| `sources.py` | `/sources` | 👥 list connectors / sync🔒. |
| `audit.py` | `/audit` | audit trail🔒. |
| `institution.py` | `/institution` | public branding (name, short code, full name) from `institution.yaml`. |
| `notices.py` | `/notices` | Staff: `POST /preview` (reach count), `POST` (send), `GET /sent` (read counts; coordinators see all). Everyone: `GET /mine`, `GET /unread-count`, `POST /{id}/read`. |
| `admin.py` | `/admin` | Admin only: `GET/POST /users`, `PATCH /users/{id}` (role, department, year, semester, division, active), `POST /users/{id}/reset-password`, `POST /users/import` (CSV), `GET /roles` (fixed permission table). |
| `analytics.py` | `/analytics` | Coordinator+: `GET ?days=` → commitments per meeting (open/overdue/done), ticket status/category/median reply hours, most-asked questions + knowledge gaps, indexed knowledge by department. |
| `calendar.py` | `/calendar` | Everyone: `GET ?days=` → academic dates (audience + department scoped) and, for staff, own open commitments with due dates; each with `days_left` + `urgency`. |
| `helpdesk.py` | `/helpdesk` | By responsibility (`auth.require_exact_roles`, no rank inheritance): categories · create · mine · close for **student + faculty**; queue read for **faculty + admin**; reply / retriage **faculty only**. Coordinators get 403. Students only ever see their own tickets and never the AI draft. |
| `timetables.py` | `/timetables` | 🔒 Coordinator+: `POST` upload (202; 200 + `duplicate` for an identical file), list, `GET /{id}` (entries + issues + diff + legend), `/source`, `/suggestions`, `PATCH` header, entries CRUD, `/publish` (`acknowledge_warnings`), `/discard`, `/reextract`; `/aliases` CRUD; `/staff`. |
| `schedule.py` | `/schedule` | 👥 `GET /mine?start=&days=` (≤42; default today in institution TZ; `has_timetable`), `GET /load`, `GET /exceptions`. Coordinator: `POST /exceptions` (validated, audited, notifies affected faculty), `DELETE /exceptions/{id}`. |

👥 = staff only (`require_staff`: faculty and above). 🔒 = requires `manager` role (see RBAC below).

### Data model (`backend/app/models/structured.py`)

Core tables: `User`, `Document`, `ProgressReport`, `ActiveInsight`, `Employee`,
`Meeting`, `Fragment`, `Commitment`, `CommitmentUpdate`, `CheckIn`, `Skill`,
`SkillCitation`, `AuditLog`, `Ticket`, `QueryLog`, `Notice`, `NoticeRecipient`,
`TimetableImport`, `TimetableEntry`, `TimetableSource` (uploaded file bytes), `FacultyAlias`, `ScheduleException` (V2 timetable).

Conventions:
- **Lists/dicts are stored as JSON strings** (DB-agnostic: SQLite in tests, Postgres in prod). E.g. `Skill.steps`, `Meeting.participants`, `AuditLog.audit_metadata`.
- `QueryLog` records each assistant question (text, asker role + department, number of sources; no user id) for analytics. Evaluation runs also land here.
- `Fragment` is the universal evidence unit; `source_type` distinguishes origin (`transcript`/`document`/`checkin`/`followup`/connector name); `visibility` decides who can retrieve it. Procedure extraction only uses `internal` fragments.
- **Timetable (V2)**: a `TimetableImport` per uploaded class timetable (`class_key`, e.g. `TY-C2`, is the stable import identity; `version`; `status` draft/published/superseded/discarded; `source_sha256`). `TimetableEntry` = one weekly slot (`weekday` 0=Mon, `"HH:MM"` times, subject, room, `faculty_abbrev`, `faculty_user_id` set only via a verified `FacultyAlias`, `issues` JSON review flags). `ScheduleException` = one date's change (DATE column `on_date`). Recurring lectures are never stored per date.
- Any new table **must** be added to the import lists in both `core/db.py:init_db()` and `tests/conftest.py`.
- **Migrations** (`backend/migrations/`, `backend/alembic.ini`): every schema change ships an Alembic revision.
  `0001_baseline` is the schema of 14 Oct 2026. Tests still build SQLite with `create_all`;
  `test_migrations.py` checks the migrations reproduce the models exactly.

### Background jobs (`backend/app/core/celery.py`)

Tasks: `process_document`, `process_transcript`, `process_timetable`, `run_daily_active_intelligence`,
`run_daily_checkins`, `run_commitment_followups`, `run_skill_extraction`,
`run_freshness_scan`, `run_deadline_reminders` (07:30). Beat schedule is defined in the same file. Task bodies use
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
lib/roles.ts               ROLE_LABEL (display names), isStaffRole(), useMe() (token-keyed /auth/me), first-login helpers.
app/password/page.tsx      First login (choose your own password) and everyday "Change password".
lib/schedule.ts            Schedule/calendar types, status labels, local-date helpers, fetchSchedule()/fetchCalendarRange().
lib/theme.ts, themeScript.ts  Light/dark: useTheme()/setTheme() (localStorage `theme`); THEME_INIT_SCRIPT runs in <head> before paint.
lib/useInstitution.ts      Public branding from /api/v1/institution.
components/layout/Sidebar.tsx   Grouped, role-filtered nav (`staff`/`coordinator`/`admin` rank flags; `roles` = exact roles, e.g. Help Desk) + ThemeToggle.
components/schedule/ScheduleView.tsx  Day/week schedule (lectures + dated items): My Work → My Schedule and Calendar → My Timetable.
components/ui/Badge.tsx         Shared status Badge (tone dot) + Tag; use for every status pill.
components/ui/EmptyState.tsx    Shared empty/unselected placeholder.
components/knowledge/SourceList.tsx  Evidence excerpts behind an AI answer (public/internal badges).
components/helpdesk/TicketBadge.tsx  Ticket status/priority styling (single source).
components/graph/GraphCanvas.tsx  Cytoscape.js graph: type filters, hub hiding, search, focus mode, neighbourhood loading
components/dashboard/InsightCard.tsx
app/
  page.tsx           Overview: greeting, today at a glance, Ask your Assistant, today's classes, tasks needing attention,
                     notifications, coming up; coordinators also get team attention, Assign work, institution alerts.
                     (staff; students are redirected to /helpdesk)
  helpdesk/          Help Desk (students + faculty): Ask a Question | Raise a Ticket side by side, my tickets, how-to guides
  calendar/          Academic Calendar (all roles) | My Timetable (staff; ScheduleView week mode)
  timetables/        Coordinator: Uploads (review: source sheet beside editable entries, initials mapping, diff, publish), Faculty initials, Date changes
  analytics/         Coordinator dashboard (commitments, tickets, questions, knowledge)
  admin/users/       Admin user management + read-only role permission table
  notices/           Notices inbox (all roles) + compose with audience filters and sent/read counts (staff)
  tickets/           Ticket queue (faculty; admin read-only): triage, AI draft + sources, reply
  login/             Auth
  relationships/     Graph map
  meetings/          Transcript upload + meeting list
  commitments/       My Work: My Schedule | My Tasks | Team (coordinators); `?view=schedule|tasks|team&task=<id>`
  assistant/         End-of-day Check-in (V1 "Faculty Desk"): follow-ups + check-in chat
  skills/            Procedures: search/filter, detail (governance, stale evidence), edit, versions + diff, approve/reject/retire, feedback, export
  chat/              Assistant (RAG chat); `?q=` pre-fills the question (never auto-sends)
  sources/           Data source upload
```

Pages talk to the API only through `apiFetch`. Design tokens (`primary`,
`danger`, `warning`, `.glass-panel`) are defined in `app/globals.css`.
**Theme**: dark is the default (no attribute). `html[data-theme="light"]` remaps the same tokens (slate scale inverted,
accent text darkened, `--color-white` → black so `white/[x]` overlays become dark tints), so pages keep their utility
classes. Use tokens/utilities, not hex colours. React must not render `data-theme` (the head script owns it).
The knowledge-graph canvas (Cytoscape) keeps its own dark palette in both themes.

---

## Cross-cutting concerns

**RBAC** — features that belong to a responsibility rather than a privilege level use
`require_exact_roles(...)` (no inheritance), e.g. the Help Desk. Otherwise roles rank
`student < employee < manager < admin` (`auth.py:_ROLE_RANK`),
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

Run: `cd backend && .venv/Scripts/python -m pytest -q` (currently **244 passing**). The local venv must match the
backend image's package versions (sqlmodel 0.0.38, SQLAlchemy 2.0.x): newer sqlmodel rejects naive datetimes and
autogenerates `UTCDateTime` columns the deployed version doesn't have.

---

## Deployment (production)
Production runs the same compose stack on an Oracle ARM VM, layered with `deploy/prod/docker-compose.prod.yml`
(127.0.0.1-only ports, restarts, Neo4j memory caps, Caddy on 80/443, `keepalive`) behind Cloudflare. Jenkins
(`deploy/jenkins/`, root `Jenkinsfile`) deploys pushes to `v2/faculty-workflow`. Settings `ALLOW_SELF_REGISTRATION` and
`SHOW_DEMO_LOGINS` (exposed on `GET /api/v1/institution`) close registration and hide demo logins in production.
Details: [DEPLOYMENT.md](DEPLOYMENT.md).

## Where to make common changes

| I want to… | Touch |
|---|---|
| Add a table / column | `models/structured.py` (+ both import lists for a table) **and** an Alembic revision in `backend/migrations/versions/` |
| Add an endpoint | new/existing `api/v1/*.py` → register in `api/router.py` |
| Add domain logic | a `services/*.py` singleton (keep routers thin) |
| Add a scheduled job | a task + beat entry in `core/celery.py` |
| Add a tunable | `core/config.py` (env-driven) |
| Add a source | a `connectors/*.py` subclass + register in `connectors/registry.py` |
| Add a UI page | `frontend/src/app/<name>/page.tsx` + add to `Sidebar.tsx` NAV |
| Customize the institution | edit `institution.yaml` (branding/settings/help desk/people) — see [CUSTOMIZING.md](CUSTOMIZING.md) |
