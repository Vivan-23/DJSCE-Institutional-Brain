# Changelog / Worklog

A running log of notable changes, newest first. **Append an entry whenever you
ship a feature, change the schema/API, or make a decision a future agent would
otherwise have to reverse-engineer.** Keep entries short; link to the files.

Format: `## YYYY-MM-DD — title` then bullets of what/why.

---

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
