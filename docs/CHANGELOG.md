# Changelog / Worklog

A running log of notable changes, newest first. **Append an entry whenever you
ship a feature, change the schema/API, or make a decision a future agent would
otherwise have to reverse-engineer.** Keep entries short; link to the files.

Format: `## YYYY-MM-DD — title` then bullets of what/why.

---

## 2026-10-25 — V2: timetable upload, review and publish (Phase 3)

- `/timetables` (coordinators) + `/api/v1/timetables`. Photos/PDFs are transcribed by a Groq vision model
  (`TIMETABLE_VISION_MODEL`, default `qwen/qwen3.8-27b`, the only vision-capable model on the project key); Word/
  Excel/CSV grids are read directly. Decision: the model only *transcribes* cells; `timetable_parser` interprets them
  with tested rules, and nothing is published without review. On the real TY C3 sample the model misplaced several
  cells by one row and misread one, so a second pass flags disagreements and the review screen shows the sheet.
- Faculty initials map to accounts only via coordinator-confirmed `FacultyAlias`; legend/initial suggestions are hints.
- Re-upload: SHA-256 dedupe for identical files; same class → next version with a diff; publishing supersedes only that
  class and moves date exceptions to matching lectures. Migration `0005_timetable_review` (source file table, review columns).
- New deps: `openpyxl`, `pymupdf`, `Pillow` (explicit).

## 2026-10-25 — V2 (branch `v2/faculty-workflow`): faculty-centric workspace, part 1

Started from V1 commit `5c5d3ad` on `main`; V1 is untouched. Driven by faculty feedback on the V1 demo.
- **Help Desk by responsibility**: `auth.require_exact_roles()` (no rank inheritance). Students + faculty use
  `/helpdesk`; faculty handle the queue; admins read it; coordinators get 403 (UI hides it too). The page shows
  Ask a Question and Raise a Ticket side by side (stacked on mobile, with a jump link). "Student Help Desk" → "Help Desk".
- **"Faculty Desk" → "End-of-day Check-in"**: faculty read the old name as "where my daily work is"; My Work is the
  daily destination. The Procedures page has a plain-language explanation.
- **Teaching timetable model** (migration `0004_timetable`, additive): `TimetableImport`, `TimetableEntry`,
  `FacultyAlias`, `ScheduleException`. Recurring lectures are expanded per date on read (never one row per date) and
  date changes never edit the weekly entry. `INSTITUTION_TIMEZONE` (default Asia/Kolkata). `/api/v1/schedule`.
  Upload/extraction, abbreviation mapping and review/publish come next.
- **Overview** rebuilt around the day: classes today, tasks needing attention (overdue / due today / blocked /
  awaiting confirmation / new), notifications (existing Notices), coming up this week, one assistant entry point.
  Coordinators add team attention and "Assign work"; system insights moved to a small coordinator-only panel.
- **My Work** split into My Schedule | My Tasks | Team (coordinators); deep links `?view=&task=`.
- **Calendar**: Academic Calendar | My Timetable (same `ScheduleView` and schedule API: one source of truth).
- **Light/dark theme** toggle (sidebar + mobile header), persisted, applied before paint; dark stays the default.
- Decision: the local test venv is pinned to the image's sqlmodel/SQLAlchemy versions (newer sqlmodel diverges).

## 2026-10-20 — IPD report as a formatted PDF

- `publication/01_ipd_report/IPD_Report_final.pdf` (43 pages, A4, Times, binding margin): title page,
  certificate, approval, declaration, acknowledgement, abstract, contents / figures / tables lists with real page
  numbers, chapters 1–8 with all 16 figures embedded and captioned, IEEE references. Source is the standalone
  `IPD_Report_final.html` (printed with Edge; front matter unnumbered, body numbered from 1).
- Content edits over `REPORT_DRAFT.md`: §2.2 written as a comparison of system categories (no unsourced product
  names), screen walkthrough per role in §6.3, objectives table gains a "Met" column, p95 stated as 10.03 s,
  algorithms numbered, tables renumbered consistently (7.1–7.8), small-sample note added to threats to validity.

## 2026-10-19 — Final evaluation run and publication tools
- Full evaluation completed (all parts) → `publication/01_ipd_report/results/RESULTS.md`; run 1 kept as baseline.
- `evaluation/publication_tools/`: `fig7_1_triage.py` (chart from RESULTS.md) and `export_report_docx.py`
  (report → Word with figures and references; needs `pypandoc-binary`). Kept here because `publication/` holds no code.
- `frontend/src/lib/renderBold.tsx`: shared `**bold**` rendering for assistant answers and ticket drafts.

## 2026-10-19 — Visual refresh: Meetings, Documents, Assistant, Faculty Desk
- **Assistant** (`app/chat`): open conversation canvas (assistant avatar + plain text, user bubbles), suggestion cards
  only before the first question, single composer with a "check the cited sources" note.
- **Meetings**: list first, as divided rows; the minutes form opens from a "Record meeting" button.
- **Faculty Desk**: follow-ups as divided rows, check-in in the same chat style; plain-language copy.
- **Documents**: plainer copy, quieter dropzone, and the pipeline explained in user terms.
- Users table status uses the shared `Badge`; assistant answers render `**bold**` instead of showing asterisks.

## 2026-10-19 — Formal list layouts, shared badges and empty states
- `components/ui/Badge.tsx` (dot + label, tones neutral/accent/success/warning/danger) replaces per-page coloured
  pills on tickets, procedures, My Work, calendar and the overview; `components/ui/EmptyState.tsx` for empty lists and
  unselected panes (ticket preview, My Work, Faculty Desk, notices, procedures).
- Procedures, Ticket Queue and Overview insights are dense divided rows in one panel instead of stacked cards;
  insight "Dismiss" shows on hover (desktop).
- Shorter page titles matching the sidebar (Overview, Procedures, Ticket Queue, Meetings, Documents, Calendar, …);
  overview stat numbers are neutral.

## 2026-10-19 — Linear-inspired visual refresh (frontend only)
- **Theme via tokens, not class rewrites**: `app/globals.css` retunes Tailwind's `slate` scale to neutral near-black
  greys and `blue` to an indigo accent (#5e6ad2), plus softer emerald/amber/rose. Every page picks this up from its
  existing classes, so keep using `slate-*`/`blue-*` for new UI. Font is Inter (`app/layout.tsx`).
- **Shell**: content sits in an inset rounded panel (`#0f1011`) on the darker app background; single slim
  demo-prototype bar (the duplicate sidebar disclaimer was removed; the bar and login notice remain).
- **Sidebar** (`components/layout/Sidebar.tsx`): grouped sections (Help Desk / Knowledge / Campus / Admin), stroke
  icons, shorter labels, compact 28px rows. Role filtering unchanged.
- **Typography sweep**: smaller semibold page titles, sentence-case labels (no `uppercase tracking-wider`), no
  `font-bold`, 10/11px text bumped to 11/12px. Raw statuses like `in_progress` render with spaces.

## 2026-10-14 — Procedures (SOPs): governance, versions, and the assistant cites them
- **Assistant uses approved procedures**: on approval a procedure is indexed (`source_type="procedure"`,
  `Fragment.skill_id`) and retrieval searches procedures separately, putting one first when it is at least as close
  as the third-best ordinary hit; prompts tell the model approved procedures outrank meeting discussion. Ticket
  drafts too. Stale, rejected and retired procedures are removed from search. Use counts recorded.
- Owner office + **review-by date** (default 1 year; shown on the owner's calendar, Active Feed reminder when due).
- **Versions**: `SkillVersion` snapshot per approval; editing an approved procedure's content opens version n+1 as a
  draft while version n stays live; "what changed" diff on the page.
- Visibility (staff only / student-facing with a plain student summary — internal steps never reach students),
  department scope, category. Students see approved student-facing ones as **How-to guides** on the Help Desk.
- Reject needs a reason; stale shows the reason and the contradicting excerpts; retire; write procedures by hand;
  "helpful / wrong" feedback (3 wrong → needs review); DOCX/PDF export and a handbook of all approved procedures.
- **Schema**: migration `0003_procedure_governance` (backfills approval and review dates); approved procedures from
  before are published on startup (`publish_missing`).

## 2026-10-14 — My Work: task progress, confirmation and check-in updates
- `Commitment` gains `progress` (0-100), `remaining`, `blocked_reason`, `assigned_by(_user_id)`, `department`,
  `marked_done_at`, `confirmed_at/by`; `CommitmentUpdate` gains `progress`, `actor`. Migration `0002_task_progress`
  (backfills department from the meeting) — applied live, no data lost.
- New status `review`: the owner (or a check-in, or a follow-up reply) saying "done" means *awaiting confirmation*;
  only a coordinator's **Confirm** sets `done`. **Send back** reopens it with a comment.
- **Security fixes**: any faculty could change anyone's task (now owner-only, coordinators for everything else),
  and the task list ignored departments (now scoped like meetings).
- Faculty Desk check-in now estimates progress, what's left and blockers per task and shows what it changed;
  uploader of a meeting recorded as "assigned by"; coordinators can create and reassign tasks; owner/assigner get
  notices on assign / blocked / done / confirmed / sent back.
- `/commitments` page is now **My Work** (sidebar "My Work & Tasks"); analytics adds blocked, to-confirm and
  average progress. Demo loader records sample progress.

## 2026-10-14 — Alembic migrations: data survives code changes
- `backend/migrations/` + `alembic.ini`; baseline `0001_baseline` = current schema. `init_db()` now runs
  `alembic upgrade head`; a database created before migrations existed is **stamped**, not re-created (verified live:
  12 users, 7 tickets, 3 notices, 153 fragments kept across a full rebuild).
- `tests/test_migrations.py`: migrations reproduce the models exactly, and a pre-migration DB keeps its rows.
- Dependency: `alembic==1.13.3`, `Mako==1.3.5`. USAGE.md §8: how to add a migration; `pg_dump` backup/restore.

## 2026-10-14 — Knowledge graph redesign (readable at scale)
- Cytoscape.js 3.34.3 replaces the hand-written canvas: zoom/pan, force layout, node size by number of connections,
  labels that appear as you zoom, no edge labels (colour = relation), type filters (documents off by default),
  "hide hubs" (nodes linked to > 25% of the graph, e.g. DJSCE), search, click-to-focus with a connections panel.
- `/graph/data` returns up to 2000 relationships (was 200) with a `truncated` flag; new `/graph/neighbors/{id}`
  loads one node's neighbourhood for graphs too large to draw.
- **Fix**: the graph ignored department scope (IT faculty could see CE meetings/documents). Document and Meeting
  nodes now carry `department` and both endpoints drop out-of-scope nodes and their edges.

## 2026-10-14 — Notices to students
- `/api/v1/notices` + `/notices` page: staff send a notice (title, message, urgent flag, optional "show until" date)
  to an audience chosen by role, department, year, semester and division, with a live "reaches N people" count.
  Faculty can only address their own department (enforced server-side); coordinators and admins any.
- **Schema**: `Notice` and `NoticeRecipient` (recipients fixed at send time → exact read counts). Inbox orders unread
  and urgent first; sidebar shows the unread count. Sends are audited.
- In-app only (decision: no email yet). Not yet: attachments, answering questions from notices in chat.
- Demo loader sends 3 sample notices (all students / CE third year / IT).

## 2026-10-14 — Admin user management
- `/api/v1/admin/*` (admin only, audited) + `/admin/users` page: create (temporary password shown once), edit role,
  department, year, semester, division; deactivate/reactivate; reset password; CSV import; read-only role table.
  Permissions stay fixed per role (decision: assign roles, don't edit permissions).
- **Schema**: `User.year`, `User.semester`, `User.division`, `User.is_active`. Deactivated users can't log in and
  their existing tokens stop working on the next request.
- **Behaviour change**: `institution.yaml` now only creates missing users; it no longer re-applies roles/departments
  on restart, so admin edits stick. 4 more synthetic students for cohort-addressed notices.
- Guardrails: no self-demotion/deactivation; the last active admin can't be removed.

## 2026-10-14 — Website data: official links in answers; more evaluation questions
- Chunks of djsce.ac.in content carry `source_url` (the Q&A's inline `(Source: …)` citation, else the file header);
  stored on `Fragment` and in Chroma metadata, returned in `sources`, shown as "Official page" links in `SourceList`.
- Website pages stay **institution-wide** even when they describe one department (they are public on the website);
  department scoping covers department-specific and internal material (CE FAQ, IT overview, CE meetings/documents).
- `qa_set.json`: +8 student questions on the website data (admissions, fees, IDEA Lab, SVKM, grading, scribe,
  governance, counselling): 33 total.

## 2026-10-14 — Analytics dashboard
- `GET /api/v1/analytics` + `/analytics` page (Coordinator+, sidebar `coordinator` flag): open/overdue commitments per
  meeting, tickets by status/category, median/mean hours to first reply, tickets open > 48 h, most-asked questions,
  knowledge gaps (questions that retrieved nothing), questions by topic and role, indexed knowledge by department.
- **Schema**: new `QueryLog` table, written by `/chat`. No user id is stored, only role and department.

## 2026-10-14 — Meeting minutes export
- `GET /api/v1/transcripts/{id}/minutes?format=docx|pdf` (Coordinator+, department scoped, audited as
  `minutes_export`). Built from stored extraction only; every file carries a "draft, verify before circulating" notice.
- **Schema**: `Meeting.decisions` (JSON list). Decisions were extracted but never saved before.
- Dependency: `reportlab==4.2.5` (+ `pillow==11.0.0`, `chardet==5.2.0`) in `requirements.lock`; the Dockerfile
  installs from the lock, not `requirements.txt`.
- Meetings page: decisions list, department picker on upload, DOCX/PDF buttons for coordinators.

## 2026-10-14 — Academic calendar and deadline reminders
- `academic_calendar:` in `institution.yaml` (synthetic demo dates, labelled as such); `calendar_service` merges it
  with each staff member's open commitments that have due dates. `GET /api/v1/calendar` (all roles, audience and
  department scoped); `/calendar` page with a reminders box (overdue / today / within 3 days).
- Daily beat `run_deadline_reminders` (07:30) posts `deadline` insights to the Active Feed, never twice for the same item.
  Reminders are computed on read, so no new table.

## 2026-10-14 — Per-department access; graph rendering; procedure extraction; demo tickets
- **Per-department access**: `departments:` in `institution.yaml`; `department` on `User`, `Fragment`, `Meeting` and
  Chroma metadata (`all` = institution-wide). Students and faculty retrieve own department + `all`; coordinators/admins
  are unrestricted (`auth.department_scope`). Filtered in the vector query and re-checked; faculty cannot list or open
  another department's meetings (404). `/ingest/file` and `/transcripts` accept `department`; registration asks for it.
  **Schema change**: new columns, so rebuild the database (`docker compose down -v`).
- Evaluation: IT questions are asked by the IT student; new `departments` part (10 cross-department probes).
- **Graph page drew nothing**: the canvas mounted only after data arrived, so the draw loop found no canvas. Fetch and
  draw are now separate effects.
- **Procedure extraction produced one skill**: greedy keyword clustering let the first cluster's keyword set absorb
  almost every fragment. Sourced fragments now cluster per meeting/document (one candidate each); max 10 per run.
- Data: 3 synthetic SOPs (revaluation, lab requisition, event approval); `ingest_institutional.py` raises 7 sample
  tickets as the demo students and staff answer/close 4 (open/answered/closed examples; `--no-demo-tickets` skips).

## 2026-10-13 — Authentic public website knowledge base
- Added `djsce_public_data/kb/` (26 files: admissions, 9 departments, exam-manual rules, placements,
  facilities, governance) from https://www.djsce.ac.in, retrieved 2026-10-13. Each file/Q&A cites its URL;
  index `djsce_public_data/sources.csv`; crawl rules in `djsce_public_data/README.md` (robots.txt, 1 req/s,
  public pages only, no personal contact data). Ingested as `visibility=public` by `ingest_institutional.py`.
- Data story is now "synthetic committee records + authentic public website information".
- Removed the mini-project's generic policy file from `public/`: it contradicted the official Exam Manual.

## 2026-10-13 — Knowledge graph fixed; laya triage engine; evaluation harness
- **Graph was empty (0 edges):** nothing ever created relationships, and meetings never reached Neo4j. Now
  `(Document)-[:MENTIONS]->`, `(Employee)-[:ATTENDED]->(Meeting)`, `(Meeting)-[:MENTIONS]->(Project)`; Document and
  Meeting nodes, colours and counts in the UI. NER cleaned (people need an honorific/roster match; bodies must name an
  institutional unit), uniqueness constraints stop duplicate nodes from concurrent workers. 0 → 53 edges; 30 noisy
  "people" → 10 real (synthetic) ones; 125 "entities" → ~20 bodies.
- Transcript parser treated header lines ("Date:", "Attendees:", "Academic Council Meeting: …") as speakers and
  created Employees for them — fixed (`_is_speaker`).
- **laya** added as an optional triage engine (`TRIAGE_ENGINES`), pinned to 0.3.21 (newest release ≥ 2 weeks old;
  the package first appeared 2026-09-18 with ~45 releases since), installed only in the `evaluator` service.
- `llm_service` retries provider rate limits (2/4/8 s). `evaluation/` harness + gold sets: triage, grounded Q&A,
  visibility leaks, commitment extraction → `publication/01_ipd_report/results/`.
- Public knowledge: added the mini-project's general academic policies (attendance, make-up exams, integrity).

## 2026-10-13 — Final-submission identity, student role, unified evidence, AI Help Desk
**Identity / data (breaking — volumes were reset).**
- `company.yaml` → `institution.yaml` (`institution:`, `helpdesk:`, `members:` keys); loader `core/institution_config.py`,
  seeder `services/institution_seed.py`, branding `GET /api/v1/institution` (was `/company`), env `INSTITUTION_CONFIG`.
- Compose project `djsce-brain`, DB/user `djsce_brain_db`/`djsce_brain_user`, containers `djsce_*`, Chroma collection
  `djsce_knowledge`, Celery app `djsce_brain`. Backend env de-duplicated with a YAML anchor. Old `company-brain` volumes removed.
- Demo cast: admin, 2 coordinators, 3 faculty, 2 students (all synthetic, `demo123`). Admin is now `admin@example.com`.

**Student role + enforced access.**
- Roles `student < employee < manager < admin`; self-registration now creates **students** (least privilege).
- `require_staff` on ingest, insights, graph, transcripts, commitments, PA, skills and sources — previously any logged-in
  user could read every internal record. Students keep auth, institution branding, chat and the help desk.
- UI role names (Student / Faculty / Committee Coordinator / System Administrator) in `frontend/src/lib/roles.ts`;
  role-filtered sidebar; students are routed to `/helpdesk`.

**One evidence pipeline + cited, visibility-aware answers.**
- `Fragment.visibility` (`internal`/`public`), mirrored in Chroma metadata. Uploaded documents now become Fragments
  (`source_type="document"`) instead of raw Chroma rows, so they feed citations and procedure extraction (internal only).
- `rag_service` rewritten on the shared `llm_service` (it had its own Groq client); filters by visibility in the vector
  query and re-checks hits; returns `sources`. `/chat` returns `sources` + `scope` (was a constant `sources_used: true`).
- Upload form/API take `visibility`. Loader fixed: it re-uploaded the meeting transcripts as documents (double-counted
  evidence); now uploads `doc_*` as internal and `public/` as public.

**Student Help Desk (merged from the Python student-chatbot mini-project).**
- Merged the mini-project's *content and ideas*, not its Django/Gemini code: 60 Computer Engineering FAQs + the IT
  department overview (contact details and the faculty roster removed) as public knowledge; its categories and quick
  questions as `institution.yaml` help-desk config; its keyword category matcher as the offline triage fallback.
- `Ticket` table, `ticket_service`, `/api/v1/helpdesk/*`, pages `/helpdesk` (students) and `/tickets` (staff queue).
  AI triage is constrained to configured categories; AI drafts are staff-only and must be sent by a human; audited.
- Procedure "approved" badge reads "Approved in Review" (was "Ratified / Active", which implied official approval).
- **Startup race fixed**: on a fresh DB the 2 uvicorn workers both ran `create_all`/seeding and one crashed
  (`duplicate key … pg_type_typname_nsp_index`). Startup now holds a Postgres advisory lock (`core/db.py:startup_lock`).
- Transcript fragments now carry the meeting title as `source_ref`; RAG labels each excerpt with its origin (fixed staff
  answers missing facts whose utterance never named the meeting). Ticket drafts use a staff-review prompt with
  `[TO CONFIRM: …]` gaps.
- Backend image no longer needs apt/curl (health check uses Python stdlib) — builds failed on a Debian mirror sync.
- Added `publication/` (brief, IPD report draft, poster content, guide-meeting template, senior samples).
- Tests: shared `tests/helpers.py:register(role=)` replaces 8 copies; +32 tests (student access, visibility, help desk,
  document fragments, profile) → **120 passing**.

## 2026-10-13 — Rebrand repository as DJSCE Institutional Brain; dedupe cleanup
- Repo now lives at github.com/Vivan-23/DJSCE-Institutional-Brain; work happens on `main` only (`demo` branch retired).
- Removed legacy Company-Brain artifacts: `mock_company_data/`, `ingest_all.py`, `generate_mock_data.py`, `COMPANY_BRAIN_OVERVIEW.txt`. `ingest_institutional.py` is the only data loader.
- Rewrote README and rebranded docs; backend defaults (`PROJECT_NAME`, `company_config` fallbacks, pyproject) and the RAG system prompt now use the institution name from `company.yaml`.
- **Kept** internal identifiers (`company.yaml`, `company_brain_db`, `cb_*` containers, `company_brain_chunks`, Celery app name) — renaming them would orphan existing Docker volumes.
- Removed the `demo@companybrain.ai` login fallback from the login page and loader (`demo@example.com` is seeded from `company.yaml`).
- Sources upload now uses `apiFetch` (consistent auth + 401 handling); added `frontend/src/lib/format.ts` replacing four duplicated date formatters.

## 2026-06-15 — Per-company customization via `company.yaml`
Single-file customization so the prototype can be forked and tailored per company
(see [CUSTOMIZING.md](CUSTOMIZING.md)).
- Added **[`company.yaml`](../company.yaml)** (repo root) — branding, settings, and
  org structure (employees/roles/managers/timezones). The one file to edit.
- `core/company_config.py` loads it (cached, safe defaults); `core/config.py`
  applies `settings` overrides; `services/company_seed.py` idempotently seeds
  Users+Employees+manager links on startup (replaces the old demo-user seeder).
- `GET /api/v1/company` serves branding; frontend `lib/useCompany.ts` makes the
  Sidebar + Login brand dynamic.
- docker-compose mounts `company.yaml` into backend/worker/beat (live-editable,
  no rebuild for profile changes); `COMPANY_CONFIG` env points at it.
- Dockerfile reordered so the baked embedding-model layer is cached across code
  changes (faster per-company rebuilds).
- Tests: +4 (config load, branding API, seed idempotency) → **88 passing**.

## 2026-06-15 — Natural-language due dates for commitments
- Added [`backend/app/services/date_parser.py`](../backend/app/services/date_parser.py)
  (`parse_due_date`): resolves LLM "due" phrases like "by Friday", "next week",
  "in 3 days", "end of month", "July 1", and ISO dates to a concrete UTC deadline
  (end of day); returns None for vague phrases ("soon", "asap").
- `commitment_service` now uses it instead of the old ISO-only `_parse_due`.
  Verified live: a transcript with "by Friday"/"next week"/"July 1"/"tomorrow"
  produced correctly dated commitments. Tests: +22 → **84 passing**.

## 2026-06-15 — Docker stack made runnable end-to-end + dependency lock
First real `docker compose up` surfaced several blockers; all fixed:
- **bcrypt conflict:** `requirements.txt` pinned `bcrypt<4.0` but `chromadb`
  requires `>=4.0.1` → unsatisfiable. Re-pinned to `bcrypt>=4.0.1,<4.1`.
- **CORS_ORIGINS crash:** typed `List[str]`, so pydantic-settings JSON-decoded the
  env string and crashed. Added `NoDecode` + a `field_validator` to parse a
  comma-separated string ([config.py](../backend/app/core/config.py)).
- **Chroma healthcheck:** the `chromadb/chroma` image is minimal (no curl/python),
  so the HTTP healthcheck always failed. Removed it; dependents use
  `service_started` (backend's Chroma connection is fault-tolerant).
- **Chroma host port:** remapped `8000→8002` (8000 is often reserved by Windows/Hyper-V).
- **Neo4j auth:** stale `neo4jdata` volume held an old password; reset volumes and
  added `start_period: 60s` to the healthcheck.
- **celery_beat perms:** writes its schedule to `/tmp/celerybeat-schedule` (the
  `/app` dir is root-owned, container runs as non-root).
- **celery healthchecks:** disabled the inherited web-server healthcheck on the
  worker/beat containers (they don't serve HTTP).
- **frontend bind + healthcheck:** set `HOSTNAME=0.0.0.0` in the frontend
  Dockerfile (Next.js standalone otherwise binds to the container id), and changed
  the healthcheck from `localhost` to `127.0.0.1` (busybox resolves localhost to
  IPv6 ::1, but the server listens on IPv4).
- **embedding model perms:** the non-root `app` user had no writable HOME, so the
  sentence-transformers cache failed (`Permission denied: '/home/app'`) and
  embeddings were disabled. Gave `app` a home, set `HF_HOME`, and **baked the
  embedding model into the image** so startup is fast and offline-safe.
- **Dependency lock:** added [`backend/requirements.lock`](../backend/requirements.lock)
  (full `pip freeze`); the Dockerfile now installs from it for deterministic,
  conflict-free builds (no pip backtracking). `requirements.txt` stays the
  human-readable source of intent. Regenerate with
  `docker compose exec backend pip freeze > backend/requirements.lock`.

## 2026-06-14 — Documentation system established
- Added `docs/` (this folder): `ARCHITECTURE.md` (codebase map), `USAGE.md`
  (setup/run/use), `CHANGELOG.md` (this file), and root `CLAUDE.md` (auto-loaded
  orientation + doc-maintenance rule).
- **Convention going forward:** update the docs in the same change as the code.
  See `CLAUDE.md` for the rule.

## 2026-06-14 — Phases 2–4 complete (PA, Skills, Connectors, Safety)
- **Phase 2 (Company PA):** `audit_service`, `pa_service` (follow-ups +
  end-of-day check-in), routes `api/v1/pa.py`, beat tasks `run_daily_checkins` /
  `run_commitment_followups`, and frontend `/assistant`.
- **Phase 3 (Skills):** `extraction_service.extract_skill()`, `skill_service`
  (keyword clustering → synthesis → citations → lifecycle → `SKILL.md` render),
  `freshness_service` (contradiction → stale + insight), routes `api/v1/skills.py`
  (incl. `/file`, `/feedback`), beat tasks `run_skill_extraction` /
  `run_freshness_scan`, and frontend `/skills`.
- **Phase 4 (Connectors + safety):** `services/connectors/` framework
  (slack/db/manual stubs + registry), `api/v1/sources.py`, `api/v1/audit.py`,
  and RBAC via `auth.require_role()` (employee < manager < admin).
- **Tests:** added `test_pa`, `test_skills`, `test_freshness`, `test_sources`,
  `test_audit`. Suite: 40 → **62 passing**.
- Fixed a pre-existing React-19 lint violation in `Sidebar.tsx` (now uses
  `useSyncExternalStore` for auth state).

## 2026-06-14 — Phase 1 frontend
- Added `/meetings` (transcript upload + meeting list) and `/commitments`
  (action items + inline status) pages; wired Sidebar nav.

## (earlier) — Phases 0–1 backend
- Schema foundation (Employee/Meeting/Fragment/Commitment/CheckIn/Skill/
  SkillCitation/AuditLog), transcript capture pipeline, commitment tracking,
  and the Phase-1 services/routes. See git history / PRD for detail.
