# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

**Before working in this repo, read [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md)** (codebase map, "where to change X").
Setup/run procedures: [`docs/USAGE.md`](docs/USAGE.md). Per-institution customization: [`docs/CUSTOMIZING.md`](docs/CUSTOMIZING.md).

## What this is
**DJSCE Institutional Brain** — a college-level (multi-year academic submission) adaptation of *Company-Brain*.
Captures institutional knowledge (committee transcripts, documents, a per-member PA) → extracts decisions /
commitments / procedures ("skills") → human review/approval → RAG assistant + knowledge graph, kept fresh.
Adapt the existing architecture with minimal change; don't rebuild it. All bundled data is **synthetic** —
never label it as official DJSCE policy (avoid statuses that imply real ratification).

## Repo / git
- Remote `origin` = github.com/Vivan-23/DJSCE-Institutional-Brain. **Work on `main` only** (the `demo` branch was retired).
- `upstream` = the original Tanishthar/Company-Brain; don't push there.

## Commands
```bash
# Full stack (Postgres, Neo4j, Chroma, Redis, backend, celery worker+beat, frontend)
docker compose up -d --build          # needs root .env (copy .env.example; GROQ_API_KEY for LLM features)

# Backend tests — no Docker needed; conftest.py mocks Chroma/Neo4j/LLM and uses SQLite
cd backend && python -m pytest -q
python -m pytest tests/test_skills.py::test_name -q   # single test

# Frontend (CI runs both of these)
cd frontend && npm run lint && npx tsc --noEmit

# Load synthetic data through the real API pipeline (stack must be running)
python ingest_institutional.py [--approve]   # DJSCE dataset (mock_institutional_data/)
python ingest_all.py                         # legacy Company-Brain dataset (mock_company_data/)

./start_public_share.ps1   # ngrok tunnel to :3000 (frontend proxies /api → backend)
```
Ports: frontend 3000, backend 8001, Chroma **8002** on host (8000 in-network), Neo4j 7474/7687, Postgres 5432, Redis 6379.
Demo login comes from `company.yaml` (`demo@example.com` / `demo123`, admin); older DBs may still have `demo@companybrain.ai`.

## Architecture (big picture)
- **Backend** FastAPI (`backend/app`). Routers in `api/v1/*` stay thin; domain logic in `services/*` module-level singletons.
  Schema = `models/structured.py`; lists/dicts are stored as **JSON strings**. New tables must be registered in
  `core/db.py:init_db()` **and** `tests/conftest.py`.
- **Async work**: ingestion endpoints return 202 and enqueue Celery tasks; all tasks + beat schedule live in
  `core/celery.py` (lazy imports inside task bodies).
- **Two ingestion paths into the same Chroma collection** (know this before touching retrieval):
  1. `/transcripts` → `transcript_service` → LLM `extraction_service` → `Meeting` + speaker `Fragment`s (Postgres + Chroma via `fragment_service`) + `Commitment`s.
  2. `/ingest/file` → `process_document` task → raw chunks straight into Chroma (no Fragment rows) + spaCy NER → Neo4j + a `Document` row.
  Only path 1 produces Fragments, so only transcripts/PA/connectors feed skill extraction and freshness.
- **Fragment** is the universal evidence unit (`source_type` = transcript/checkin/followup/connector name). Skills cite fragments via
  `SkillCitation`; the frontend `EvidencePanel` groups duplicate excerpts but must keep every citation's provenance.
- **Skill lifecycle** draft → approved → stale (freshness_service contradiction scan) → deprecated/rejected; rendered to `SKILL.md`.
- **LLM**: `llm_service` (Groq) with `is_available` graceful degradation. Exception: `rag_service` builds its own Groq client.
- **People exist twice**: Postgres `Employee` (via `employee_service`, from transcripts/company.yaml) and Neo4j `:Employee`
  (from NER, keyed by synthesized `name@company.internal` emails). They are not linked.
- **RBAC**: `auth.require_role("manager")`; ranks `employee < manager < admin`.
- **Frontend** Next.js 16 / React 19 (`frontend/src`), non-standard version with stricter lint — read `frontend/AGENTS.md`
  (e.g. no synchronous `setState` in effects). All calls should go through `lib/api.ts:apiFetch`; `next.config.ts` rewrites
  `/api/*` to the backend, so `NEXT_PUBLIC_API_URL` is empty in Docker.
- **Branding/org**: root `company.yaml`, mounted read-only into backend containers and seeded on startup (`company_seed.py`).

## Documentation rule
In the same change: structure/route/table/job/page changes → `docs/ARCHITECTURE.md`; run/usage changes → `docs/USAGE.md`;
features, schema/API changes, non-obvious decisions → `docs/CHANGELOG.md`. Bump each doc's "Last verified" date when confirmed.
