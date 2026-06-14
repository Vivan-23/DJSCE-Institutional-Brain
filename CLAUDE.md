# Company Brain — agent orientation

**Before working in this repo, read [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md).**
It's the codebase map (services, routes, models, jobs, "where to change X") and
exists so you don't have to re-read the whole codebase each session. For setup,
running, and feature procedures, see [`docs/USAGE.md`](docs/USAGE.md).

## What this is
The executable knowledge layer for AI agents: capture company knowledge
(meeting transcripts + a per-employee Company PA) → synthesize **executable
skills** → human review/approval → serve to agents, kept fresh. Product spec:
[`PRD`](PRD).

## Documentation maintenance rule (important)
Keep docs in lockstep with the code. **In the same change that you:**
- change structure / add a service, route, table, job, or page → update [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md);
- change how to run or use something → update [`docs/USAGE.md`](docs/USAGE.md);
- ship a feature, change schema/API, or make a non-obvious decision → append to [`docs/CHANGELOG.md`](docs/CHANGELOG.md).

If a doc and the code disagree, fix the doc (or the code) — don't leave it stale.
Each doc has a "Last verified" date; bump it when you confirm it's current.

## Fast facts
- Backend: FastAPI (`backend/app`), port **8001**. Frontend: Next.js 16/React 19 (`frontend`), port **3000**.
- Domain logic lives in `services/*` singletons; keep routers thin.
- Schema = `backend/app/models/structured.py`; new tables must be added to `core/db.py:init_db()` **and** `tests/conftest.py`.
- Scheduled jobs + Celery tasks: `backend/app/core/celery.py`.
- RBAC: `auth.require_role()`; roles `employee < manager < admin`. Demo user `demo@companybrain.ai` / `demo123` (admin).
- Tests (no Docker needed): `cd backend && .venv/Scripts/python -m pytest -q` → **84 passing**.
- Frontend is a non-standard Next.js with stricter lint — see `frontend/AGENTS.md` (e.g. no synchronous `setState` in effects).
