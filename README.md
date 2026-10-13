# DJSCE Institutional Brain

**An institutional knowledge and governance platform for Dwarkadas J. Sanghvi College of Engineering (DJSCE).**
It captures what committees, departments and faculty decide and agree to do — from meeting transcripts,
reference documents and a per-member assistant — and turns it into searchable, evidence-backed
institutional knowledge: decisions, tracked commitments, documented procedures, and a knowledge graph.

> ⚠️ **Demonstration data.** Every meeting, document, person and procedure bundled in this repository
> (`mock_institutional_data/`, `company.yaml`) is **synthetic**. Nothing here is an official DJSCE record,
> decision or approved policy.

Built on the open-source *Company Brain* architecture and adapted for a college setting.

---

## 📖 Documentation

| Doc | Purpose |
|---|---|
| **[docs/USAGE.md](docs/USAGE.md)** | Setup, running (Docker or local dev), feature walkthrough, troubleshooting |
| **[docs/ARCHITECTURE.md](docs/ARCHITECTURE.md)** | Codebase map — services, routes, models, jobs, "where to change X" |
| **[docs/CUSTOMIZING.md](docs/CUSTOMIZING.md)** | Institutional profile (`company.yaml`): branding, settings, people and roles |
| **[docs/CHANGELOG.md](docs/CHANGELOG.md)** | What changed and why |

---

## The problem

Institutional knowledge in a college is scattered across committee minutes, circulars, SOPs, accreditation
working papers and people's memory. Decisions get made in an Academic Council or IQAC meeting, action items
are assigned, and then the trail goes cold. When a procedure (exam moderation, lab readiness, curriculum
review) needs to be followed again, nobody can find *how it was actually done* or *who agreed to what*.

## What it does

| Area | What you get |
|---|---|
| **Meeting intelligence** | Paste a committee transcript → summary, participants, decisions and commitments (with owners and due dates) are extracted. |
| **Commitments** | Every action item is tracked through `open → in_progress → blocked → done / dropped`. |
| **Institutional Assistant (PA)** | Each member gets natural-language follow-ups on their open commitments and a short end-of-day check-in — no forms. |
| **Procedures** | Related evidence is clustered and synthesized into structured procedures (trigger, steps, decision rules, guardrails, escalation), each citing its source excerpts. A coordinator reviews and approves them. |
| **Evidence & provenance** | The Evidence panel groups duplicate excerpts while keeping every underlying citation inspectable. |
| **Knowledge graph** | People and bodies mentioned in documents are linked in Neo4j and visualised. |
| **Q&A assistant** | RAG chat grounded in indexed transcripts and documents. |
| **Freshness** | When new evidence contradicts an approved procedure, it is flagged `stale` and routed back for review. |

---

## Architecture

```mermaid
flowchart TD
    T["Committee transcripts"] --> X["LLM extraction"]
    D["Reference documents / SOPs"] --> P["Chunk + embed + NER"]
    PA["Institutional Assistant<br/>follow-ups · check-ins"] --> F
    X --> M["Meetings · decisions"]
    X --> C["Commitments"]
    X --> F["Evidence fragments"]
    F --> S["Procedure synthesis (cited)"]
    S --> R["Coordinator review & approval"]
    R --> FR["Freshness scan → stale"]
    P --> V[("ChromaDB")]
    F --> V
    P --> G[("Neo4j graph")]
    M & C & S --> PG[("PostgreSQL")]
    V --> Q["Q&A assistant (RAG)"]
```

| Layer | Technology |
|---|---|
| Frontend | Next.js 16, React 19, TypeScript, Tailwind CSS v4 |
| Backend API | FastAPI, Python 3.11 |
| Auth | JWT, role-based access: `employee < manager < admin` |
| Relational store | PostgreSQL (SQLModel) |
| Vector search | ChromaDB + sentence-transformers |
| Graph | Neo4j |
| LLM | Groq (configurable model) |
| Background jobs | Celery + Redis (worker + beat) |
| Deployment | Docker Compose |

---

## Quick start

```bash
cp .env.example .env               # set GROQ_API_KEY and SECRET_KEY
docker compose up -d --build
python ingest_institutional.py     # load the synthetic DJSCE dataset (optional: --approve)
```

Open http://localhost:3000 and sign in with the demo account from `company.yaml`
(`demo@example.com` / `demo123`). Full instructions: [docs/USAGE.md](docs/USAGE.md).

---

## API overview

All endpoints except `/health`, `/api/v1/company` and auth require a Bearer token. 🔒 = `manager` role or higher.

| Method | Path | Description |
|---|---|---|
| `POST` | `/api/v1/auth/login` · `/register` | Obtain a JWT |
| `POST` / `GET` | `/api/v1/transcripts` · `/{id}` | Ingest a transcript (queued) / list and fetch meetings |
| `POST` | `/api/v1/ingest/file` | Upload a .txt / .pdf / .docx reference document (queued) |
| `GET` · `PATCH` | `/api/v1/commitments` · `/mine` · `/{id}` | List commitments / update status |
| `GET` · `POST` | `/api/v1/pa/followups` · `/pa/checkin` … | Assistant follow-ups and end-of-day check-in |
| `GET` | `/api/v1/skills` · `/{id}` | List procedures / full procedure with citations |
| `POST` | `/api/v1/skills/extract` | 🔒 Run procedure extraction |
| `PATCH` · `POST` | `/api/v1/skills/{id}` · `/approve` · `/reject` | 🔒 Edit and review procedures |
| `GET` | `/api/v1/skills/{id}/file` | Rendered `SKILL.md` (approved only) |
| `POST` | `/api/v1/chat` | Q&A over indexed knowledge |
| `GET` | `/api/v1/graph/data` · `/stats` | Knowledge-graph data |
| `GET` · `POST` | `/api/v1/sources` · `/{name}/sync` | Source connectors (sync 🔒) |
| `GET` | `/api/v1/audit` | 🔒 Audit trail |
| `GET` | `/health` | Health check |

Interactive docs: http://localhost:8001/docs

---

## Current scope and limitations

- Meeting capture is transcript-based (no live meeting bot).
- Slack / database connectors are credential-aware stubs; the `manual` connector accepts pushed items.
- Uploaded documents are indexed for Q&A and the graph but do not yet feed procedure extraction.
- Roles are the generic `employee < manager < admin`; a DJSCE display mapping (Faculty / Committee Coordinator / System Administrator) is planned, not yet implemented.

## Tests

```bash
cd backend && python -m pytest -q        # mocks all external services; no Docker needed
cd frontend && npm run lint && npx tsc --noEmit
```

## License

MIT
