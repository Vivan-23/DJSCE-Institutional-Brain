# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

**Before working in this repo, read [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md)** (codebase map, "where to change X").
Setup/run procedures: [`docs/USAGE.md`](docs/USAGE.md). Per-institution customization: [`docs/CUSTOMIZING.md`](docs/CUSTOMIZING.md).

## What this is
**DJSCE Institutional Brain** — a college-level (multi-year academic submission) adaptation of *Company-Brain*.
Captures institutional knowledge (committee transcripts, documents, a Faculty Desk PA) → extracts decisions /
commitments / procedures ("skills") → human review/approval → cited RAG assistant + knowledge graph, kept fresh.
Students use a Help Desk: instant answers from *public* knowledge, or tickets that AI triages/drafts and staff answer.
Adapt the existing architecture with minimal change; don't rebuild it. All bundled data is **synthetic** —
never label it as official DJSCE policy (avoid statuses that imply real ratification).

## Repo / git
- Layout: **development** = `backend/`, `frontend/`, `docs/`, `mock_institutional_data/`, root scripts;
  **publication** = `publication/` (mentor brief, IPD report, poster, slides, paper, guide-meeting notes). Never put code
  in `publication/` or report drafts in `docs/`. Report/poster numbers must come from reproducible runs (`TBD` until then).
- Remote `origin` = github.com/Vivan-23/DJSCE-Institutional-Brain. **Work on `main` only** (the `demo` branch was retired).
- `upstream` = the original Tanishthar/Company-Brain; don't push there.

## Commands
```bash
# Full stack (Postgres, Neo4j, Chroma, Redis, backend, celery worker+beat, frontend)
docker compose up -d --build          # needs root .env (copy .env.example; GROQ_API_KEY for LLM features)

# Backend tests — conftest.py mocks Chroma/Neo4j/LLM and uses SQLite. Needs the backend deps; if the local
# Python env is broken, run them in the built image: copy backend/app + tests + institution.yaml into
# /tmp inside `docker run --entrypoint sh djsce-brain-backend` and run pytest there.
cd backend && python -m pytest -q
python -m pytest tests/test_skills.py::test_name -q   # single test

# Frontend (CI runs both of these)
cd frontend && npm run lint && npx tsc --noEmit

# Load synthetic data through the real API pipeline (stack must be running)
python ingest_institutional.py [--approve]   # transcripts, doc_* (internal), public/ (student-visible)

./start_public_share.ps1   # ngrok tunnel to :3000 (frontend proxies /api → backend)
```
Ports: frontend 3000, backend 8001, Chroma **8002** on host (8000 in-network), Neo4j 7474/7687, Postgres 5432, Redis 6379.
Demo logins come from `institution.yaml` (all `demo123`): `admin@example.com`, `aditi.rao@example.com` (coordinator),
`karan.shah@example.com` (faculty), `aarav.desai@example.com` (student). Compose project `djsce-brain`, DB `djsce_brain_db`.

## Architecture (big picture)
- **Backend** FastAPI (`backend/app`). Routers in `api/v1/*` stay thin; domain logic in `services/*` module-level singletons.
  Schema = `models/structured.py`; lists/dicts are stored as **JSON strings**. New tables must be registered in
  `core/db.py:init_db()` **and** `tests/conftest.py`.
- **Async work**: ingestion endpoints return 202 and enqueue Celery tasks; all tasks + beat schedule live in
  `core/celery.py` (lazy imports inside task bodies).
- **One evidence pipeline**: everything indexed is a `Fragment` written via `fragment_service` (Postgres row + Chroma vector).
  `/transcripts` → speaker fragments + `Meeting` + `Commitment`s; `/ingest/file` → `process_document` → chunk fragments
  (`source_type="document"`, `source_ref`=filename) + spaCy NER → Neo4j. Never write to Chroma directly.
- **Visibility is a security boundary**: `Fragment.visibility` (`internal` default / `public`) is mirrored in Chroma metadata.
  `rag_service.retrieve(public_only=True)` (students) filters in the query *and* re-checks hits. Procedure extraction only
  uses `internal` fragments. New ingestion paths must set visibility deliberately.
- Skills cite fragments via `SkillCitation`; the frontend `EvidencePanel` groups duplicate excerpts but must keep every
  citation's provenance. Chat and ticket drafts return `sources`, rendered by `components/knowledge/SourceList.tsx`.
- **Skill lifecycle** draft → approved → stale (freshness_service contradiction scan) → deprecated/rejected; rendered to `SKILL.md`.
- **LLM**: every caller uses `llm_service` (Groq) and degrades when `is_available` is false.
- **Help desk** (`ticket_service`, `/helpdesk`): triage chain LLM → keyword fallback (only categories from `institution.yaml`);
  staff-only AI draft + sources; a human sends the reply. Non-staff get 404 for others' tickets and never see `ai_*` fields.
- **People exist twice**: Postgres `Employee` (staff only, via `employee_service` / `institution_seed`) and Neo4j `:Employee`
  (from NER, keyed by synthesized `name@<email_domain>`). They are not linked. Students have a `User` but no `Employee`.
- **RBAC**: ranks `student < employee < manager < admin` (UI: Student / Faculty / Committee Coordinator / System Administrator,
  `frontend/src/lib/roles.ts`). Internal routers use `Depends(require_staff)`; elevated actions `require_role("manager")`.
  Self-registration creates students. Tests get a role via `tests/helpers.py:register(client, email, role=...)`.
- **Frontend** Next.js 16 / React 19 (`frontend/src`), non-standard version with stricter lint — read `frontend/AGENTS.md`
  (e.g. no synchronous `setState` in effects). All calls should go through `lib/api.ts:apiFetch`; `next.config.ts` rewrites
  `/api/*` to the backend, so `NEXT_PUBLIC_API_URL` is empty in Docker.
- **Profile**: root `institution.yaml` (branding, settings, help-desk categories, members), mounted read-only into the
  backend containers and seeded on startup (`institution_seed.py`).

## Documentation rule
In the same change: structure/route/table/job/page changes → `docs/ARCHITECTURE.md`; run/usage changes → `docs/USAGE.md`;
features, schema/API changes, non-obvious decisions → `docs/CHANGELOG.md`. Bump each doc's "Last verified" date when confirmed.
