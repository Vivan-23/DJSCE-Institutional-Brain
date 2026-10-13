# Usage & Operating Procedures

How to set up, run, and use DJSCE Institutional Brain. For the codebase map see
[ARCHITECTURE.md](ARCHITECTURE.md). Last verified: 2026-10-13.

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

On first boot the people in `institution.yaml` are seeded. Demo logins (all `demo123`): **`admin@example.com`** (System Administrator), `aditi.rao@example.com` (Committee Coordinator), `karan.shah@example.com` (Faculty), `aarav.desai@example.com` (Student). The login page has one-click buttons for each.

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

Log in at http://localhost:3000 with a demo account (or register — self-registration
always creates a **student** account). Students land on the **Help Desk**; staff on
the governance overview.

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

### C. Institutional Assistant / Faculty Desk  (`/assistant`)
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

### E. Documents & Sources  (`/sources` + API)
- Upload a .txt/.pdf/.docx and choose **Internal** (staff only, the default) or
  **Public** (students can get answers from it). Chunks become Fragments, so
  internal documents also feed procedure extraction and citations.
- `GET /api/v1/sources` lists connectors and whether they're configured.
- `POST /api/v1/sources/{name}/sync` (manager) ingests fragments. Live Slack/email/
  ticket pulls are post-V1 stubs; the **`manual`** connector accepts pushed items
  today:
  ```bash
  curl -X POST http://localhost:8001/api/v1/sources/manual/sync \
    -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
    -d '{"items":[{"content":"Refunds over $500 need manager approval","author":"Dana"}]}'
  ```

### F. Student Help Desk  (`/helpdesk`, `/tickets`)
- **Students** (`/helpdesk`): one-click quick questions per category (from
  `institution.yaml`) are answered instantly from *public* knowledge, with sources.
  If that doesn't help, **Raise a ticket** — it is triaged (category, priority,
  owning office) and listed under *My tickets* with the eventual reply.
- **Staff** (`/tickets`): the queue shows the triage result and method (AI or
  keyword fallback), plus an **AI-suggested reply with its sources** (an amber
  warning appears if it used internal sources). Edit it and **Send reply** — the
  student never sees the draft, only what you send.

### G. Agent consumption
An agent runtime fetches approved skills and reports outcomes:
```
GET  /api/v1/skills                  → list (metadata)
GET  /api/v1/skills/{id}/file        → executable SKILL.md
POST /api/v1/skills/{id}/feedback    → {agent_id, outcome, detail}   (audited)
```

### H. Audit  (`/api/v1/audit`, manager)
Every autonomous action (extraction, approval, skill-use, check-in, follow-up,
sync, ticket create/triage/reply) is logged. Filter by `?action=` or `?target_id=`.

---

## 5. Roles

| Role id | Shown as | Can |
|---|---|---|
| `student` | Student | Help Desk (ask, raise/track own tickets), assistant over **public** knowledge only |
| `employee` | Faculty | Everything internal: meetings, commitments, Faculty Desk, procedures (read), graph, documents, ticket queue |
| `manager` | Committee Coordinator | + approve/reject/extract procedures, sync sources, audit log |
| `admin` | System Administrator | everything |

New self-registrations are `student`. Change a role in `institution.yaml` (then
restart the backend) or by setting `User.role` in the DB — takes effect without
re-login. Enforcement is in the backend (`require_staff` / `require_role`); the
sidebar only hides what the API would refuse anyway.

---

## 6. Loading the demo data

Committee data (meetings, people, internal procedures in `mock_institutional_data/`
and `institution.yaml`) is **synthetic** and not an official DJSCE record. It is combined
with authentic public information from the college website (`djsce_public_data/kb/`,
26 files, each citing its source URL and retrieval date 2026-10-13; see
[`djsce_public_data/README.md`](../djsce_public_data/README.md) and `sources.csv`). People are pre-seeded from [`institution.yaml`](../institution.yaml)
(sign in as `admin@example.com` / `demo123`, or any listed member).

With the stack running and `GROQ_API_KEY` set, load the dataset in
[`mock_institutional_data/`](../mock_institutional_data) through the real pipeline:

```bash
pip install requests
python ingest_institutional.py            # transcripts + reference documents
python ingest_institutional.py --approve  # also auto-approve extracted procedures
```

The loader logs in, posts the committee transcripts (→ **Meetings** +
**Commitments**), uploads `doc_*.txt` as **internal** documents and everything in
`public/` (department FAQs, curriculum, outcomes — from the student-chatbot
mini-project, contact details removed) as **public** documents, uploads every file in
`djsce_public_data/kb/` (admissions, departments, exam-manual rules, placements,
facilities, governance) as **public** documents, waits for the worker, then triggers
procedure extraction (internal fragments only).

**Suggested demo path:** sign in as the **Student** → Help Desk quick question →
raise a ticket → sign in as **Faculty** → Help Desk Queue (review AI draft, reply) →
Governance Overview → Meetings → Commitments →
Procedures (review, open the Evidence panel) → Institutional Assistant (ask a
question about a committee decision) → Knowledge Graph.

### Remote demo (ngrok)

`./start_public_share.ps1` (PowerShell) brings the stack up, checks backend
health, and opens an ngrok tunnel to the frontend on port 3000. The frontend
proxies `/api/*` to the backend (see `frontend/next.config.ts`), so only one
public URL is needed and no database port is exposed. Requires `ngrok` on PATH
and an authenticated ngrok account.

---

## 7. Evaluation (numbers for the report)

With the stack up and the dataset loaded:

```bash
docker compose --profile eval run --rm evaluator
```

It measures help-desk triage (keyword vs LLM vs the optional laya classifier), grounded
Q&A, student visibility leaks and commitment extraction, and writes
`publication/01_ipd_report/results/RESULTS.md`. The first run downloads laya's model
(about 4 minutes, cached afterwards). To try laya in the app itself, install
`laya==0.3.21` in the backend image and set `TRIAGE_ENGINES=laya,llm,keyword`.
Details: [`evaluation/README.md`](../evaluation/README.md).

## 8. Testing

```bash
cd backend && .venv/Scripts/python -m pytest -q      # no Docker needed
```

Frontend checks:
```bash
cd frontend && npx tsc --noEmit && npx eslint src
```

---

## 9. Troubleshooting

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
| `djsce_chroma` unhealthy / blocks backend | Fixed — image has no curl; healthcheck removed, dependents use `service_started`. |
| `djsce_neo4j` unhealthy: "authentication failure" | Stale `neo4jdata` volume with an old password. `docker compose down -v` then `up` to re-init. |
| Port bind error on 8000/3000/5432 | Another process/old container holds it. `docker compose down --remove-orphans`, or remap the host port. |
| `celery_beat` exits: `Permission denied: 'celerybeat-schedule'` | Fixed — beat writes to `/tmp` (non-root container). |
| `djsce_frontend` works on host but shows unhealthy | Fixed — `HOSTNAME=0.0.0.0` so Next binds all interfaces. |
| Backend log: "Failed to load embedding model — Permission denied: '/home/app'" | Fixed — `app` user now has a writable HOME/`HF_HOME` and the model is baked into the image. |
