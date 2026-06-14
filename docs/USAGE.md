# Usage & Operating Procedures

How to set up, run, and actually *use* Company Brain. For the codebase map see
[ARCHITECTURE.md](ARCHITECTURE.md). Last verified: 2026-06-14.

---

## 1. Prerequisites

- **Docker Desktop** (easiest full-stack run), or for local dev: **Python 3.11**, **Node 20+**.
- A **Groq API key** (free at https://console.groq.com). Without it the app still
  runs, but LLM features (extraction, PA reasoning, skill synthesis, freshness)
  fall back to degraded/no-op behavior.

---

## 2. First-time setup

```bash
# 1. Create your env file from the template, then fill in secrets.
cp .env.example .env
#    - GROQ_API_KEY=...           (your Groq key)
#    - SECRET_KEY=...             (python -c "import secrets; print(secrets.token_hex(32))")
```

`.env` is git-ignored. Database/Neo4j/Chroma/Redis defaults already match
`docker-compose.yml`, so for the Docker path you only need the two secrets.

---

## 3. Running the system

### Option A — Docker Compose (full stack, recommended)

```bash
docker compose up --build
```

Brings up Postgres, Neo4j, ChromaDB, Redis, the API, a Celery **worker**, a
Celery **beat** scheduler, and the frontend. Then open:

- Frontend: http://localhost:3000
- API docs (Swagger): http://localhost:8001/docs
- Health: http://localhost:8001/health
- Neo4j browser: http://localhost:7474
- ChromaDB: http://localhost:**8002** (container port 8000 is remapped to avoid the Windows reserved-port range)

> **Dependencies are locked.** The backend image installs from
> [`backend/requirements.lock`](../backend/requirements.lock) (a full `pip freeze`)
> so builds are deterministic and never re-resolve/backtrack. `requirements.txt`
> remains the human-readable source of intent. After changing a dependency,
> regenerate the lock:
> ```bash
> docker compose exec backend pip freeze > backend/requirements.lock
> ```

On first boot a demo admin is seeded — **`demo@companybrain.ai` / `demo123`**.

### Option B — Local dev (hot reload)

You still need the datastores. Run just those in Docker:

```bash
docker compose up postgres neo4j chromadb redis
```

Then, in separate terminals:

```bash
# Backend API  (from backend/, venv already exists at backend/.venv)
cd backend
.venv/Scripts/python -m uvicorn app.main:app --reload --port 8001

# Celery worker (background tasks: transcript/skill processing)
cd backend
.venv/Scripts/python -m celery -A app.core.celery worker --loglevel=info --pool=solo   # --pool=solo on Windows

# Celery beat (scheduled check-ins, follow-ups, extraction, freshness)
cd backend
.venv/Scripts/python -m celery -A app.core.celery beat --loglevel=info

# Frontend
cd frontend
npm install
npm run dev
```

> **Note:** for local dev set `DATABASE_URL` etc. to `localhost` (that's the
> default in `.env.example`). Inside Docker the service names (`postgres`, `redis`,
> …) are injected by compose.

---

## 4. Using the product

Log in at http://localhost:3000 with the demo account (or register a new one —
new users get the `employee` role).

### A. Capture a meeting → commitments  (`/meetings`)
1. Go to **Meetings**, paste a transcript (speaker-labelled lines like
   `Alex: I'll own the API.` work best) and a title, click **Process Transcript**.
2. The transcript is queued to Celery. Within a few seconds the meeting appears
   with an extracted summary, participants, and decisions; commitments are created
   with owners resolved to employees.
3. View them under **Commitments**.

### B. Track commitments  (`/commitments`)
- Filter by status, toggle **Assigned to me**, and change a commitment's status
  inline (`open → in_progress → blocked → done → dropped`). Updates persist via
  `PATCH /api/v1/commitments/{id}`.

### C. Company PA  (`/assistant`)
- **Follow-ups:** open/overdue commitments (older than
  `COMMITMENT_FOLLOWUP_HOURS`, default 48h) show a natural-language nudge. Reply
  in plain text — the PA records a `CommitmentUpdate`, infers a status change, and
  writes a Fragment.
- **End-of-day check-in:** just describe your day. The PA replies, maps what you
  said onto your open commitments (status + summary), captures new commitments,
  and saves your words as Fragments. Click **Mark check-in complete** to close it.

### D. Skills  (`/skills`)
1. Once enough Fragments exist, click **Run extraction** (manager role) — or wait
   for the nightly job. Fragments are clustered and synthesized into candidate
   **skills** (trigger, steps, decision rules, guardrails, escalation) with
   citations back to the evidence.
2. Expand a candidate to review it. A **manager** can **Approve** or **Reject**.
3. **View skill file** renders the agent-consumable `SKILL.md`. The file endpoint
   (`GET /api/v1/skills/{id}/file`) only serves **approved** skills.
4. The **freshness** job flags an approved skill `stale` when new evidence
   contradicts it and raises an insight on the Active Feed.

### E. Sources  (`/sources` + API)
- `GET /api/v1/sources` lists connectors and whether they're configured.
- `POST /api/v1/sources/{name}/sync` (manager) ingests fragments. Live Slack/email/
  ticket pulls are post-V1 stubs; the **`manual`** connector accepts pushed items
  today:
  ```bash
  curl -X POST http://localhost:8001/api/v1/sources/manual/sync \
    -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
    -d '{"items":[{"content":"Refunds over $500 need manager approval","author":"Dana"}]}'
  ```

### F. Agent consumption (the deliverable)
An agent runtime fetches approved skills and reports outcomes:
```
GET  /api/v1/skills                  → list (metadata)
GET  /api/v1/skills/{id}/file        → executable SKILL.md
POST /api/v1/skills/{id}/feedback    → {agent_id, outcome, detail}   (audited)
```

### G. Audit  (`/api/v1/audit`, manager)
Every autonomous action (extraction, approval, skill-use, check-in, follow-up,
sync) is logged. Filter by `?action=` or `?target_id=`.

---

## 5. Roles

`employee < manager < admin`. New registrations are `employee`. Reviewing/
approving skills, running extraction, syncing sources, and reading the audit log
need `manager`+. Promote a user by setting `User.role` (DB) — no re-login needed.
The seeded demo user is `admin`.

---

## 6. Bulk-loading sample data

`mock_company_data/` holds sample meeting/doc `.txt` files. With the API running:

```bash
python ingest_all.py     # posts every .txt to /api/v1/ingest/file
```

(`generate_mock_data.py` regenerates the sample set.)

---

## 7. Testing

```bash
cd backend && .venv/Scripts/python -m pytest -q      # 84 passing, no Docker needed
```

Frontend checks:
```bash
cd frontend && npx tsc --noEmit && npx eslint src
```

---

## 8. Troubleshooting

| Symptom | Likely cause / fix |
|---|---|
| API exits with `GROQ_API_KEY`/`SECRET_KEY` validation error | `.env` missing those keys. Required (no defaults). |
| Transcript ingests but no commitments/summary | Celery worker not running, or `GROQ_API_KEY` invalid (extraction degrades to empty). |
| Skill file returns 409 | Skill isn't `approved` — only approved skills export. |
| 403 on approve/extract/sync/audit | Caller isn't `manager`+. |
| Follow-ups never appear | Commitment not yet older than `COMMITMENT_FOLLOWUP_HOURS`, or not assigned to your employee. |
| Frontend 401 loops to /login | Token expired (`ACCESS_TOKEN_EXPIRE_MINUTES`) — log in again. |
| Windows: Celery worker crashes on start (local dev) | Use `--pool=solo`. |
| `pytest` PermissionError deleting test DB | Known Windows file-handle quirk; `engine.dispose()` handles it — rerun. |
| `docker compose up` fails: bcrypt/chromadb version conflict | Fixed — `bcrypt>=4.0.1,<4.1`. If you edited deps, regenerate the lock (above). |
| Backend exits: `error parsing value for field "CORS_ORIGINS"` | Fixed — config now parses a comma-separated string. Set `CORS_ORIGINS=a,b` (not JSON). |
| `cb_chroma` unhealthy / blocks backend | Fixed — image has no curl; healthcheck removed, dependents use `service_started`. |
| `cb_neo4j` unhealthy: "authentication failure" | Stale `neo4jdata` volume with an old password. `docker compose down -v` then `up` to re-init. |
| Port bind error on 8000/3000/5432 | Another process/old container holds it. `docker compose down --remove-orphans`, or remap the host port. |
| `celery_beat` exits: `Permission denied: 'celerybeat-schedule'` | Fixed — beat writes to `/tmp` (non-root container). |
| `cb_frontend` works on host but shows unhealthy | Fixed — `HOSTNAME=0.0.0.0` so Next binds all interfaces. |
| Backend log: "Failed to load embedding model — Permission denied: '/home/app'" | Fixed — `app` user now has a writable HOME/`HF_HOME` and the model is baked into the image. |
