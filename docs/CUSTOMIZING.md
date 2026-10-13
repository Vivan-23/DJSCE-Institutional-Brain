# Customizing the institution profile

Branding, settings, help-desk routing and the people roster all live in **one
file — [`institution.yaml`](../institution.yaml)** at the repo root. On startup the
backend reads it and reconfigures itself. Last verified: 2026-10-14.

---

## Sections

| Section | Drives | Where it shows up |
|---|---|---|
| `institution.name` / `short_code` / `full_name` | UI branding (sidebar, login page) and the assistant's name | `GET /api/v1/institution` |
| `institution.email_domain` | domain for derived graph identities | document NER → Neo4j |
| `settings.pa_checkin_hour` | Faculty Desk end-of-day check-in time | Celery beat schedule |
| `settings.commitment_followup_hours` | when a commitment counts as stale | follow-up scans |
| `helpdesk.categories[]` | ticket categories, owning office, keyword fallback, quick questions | `/helpdesk`, ticket triage |
| `departments[]` | department codes and names; scopes what students/faculty retrieve | registration form, upload form, retrieval |
| `members[]` | people, roles, departments, reporting lines | seeded into the DB |

Seeding is **idempotent** (matched by email): edit, restart, and the DB matches.
Removing a person does **not** delete them — that stays a deliberate manual action.

### Members

```yaml
members:
  - name: "Dr. Aditi Rao"          # synthetic person
    email: "aditi.rao@example.com"
    role: "manager"                # student | employee | manager | admin
    title: "Academic Coordinator, Academic Council"
    department: "CE"               # code (or full name) from `departments:`
    manager: "admin@example.com"   # reporting coordinator's email
    timezone: "Asia/Kolkata"       # default
    password: "demo123"            # set → this person gets a login
```

| `role` | Shown as | Notes |
|---|---|---|
| `student` | Student | Login only — no Employee row, never assigned commitments |
| `employee` | Faculty | Staff: internal data, Faculty Desk, ticket queue |
| `manager` | Committee Coordinator | + approve procedures, extraction, sources, audit |
| `admin` | System Administrator | everything |

Unknown roles are skipped with a warning (never silently granted access).

### Departments

```yaml
departments:
  - { code: "CE", name: "Computer Engineering" }
  - { code: "IT", name: "Information Technology" }
```

Students and faculty retrieve their own department's material plus institution-wide (`all`)
material; coordinators and administrators see every department. Tag material when ingesting
(the upload form's *Department* menu, or `department` in the API); untagged material is
institution-wide. A student or faculty member with no department sees only institution-wide
material. Leave `departments:` out to disable scoping.

### Academic calendar

```yaml
academic_calendar:
  note: "Shown above the calendar (e.g. where the official calendar lives)."
  events:
    - { date: "2026-11-25", end: "2026-12-11", title: "End-semester theory examinations", kind: exam }
    - { date: "2026-10-26", title: "Elective registration closes", kind: deadline, audience: students, department: CE }
```

`kind`: term / exam / holiday / deadline / event. `audience`: all / students / staff. `department`: a code
or `all`. Events with a bad date or audience are skipped with a warning. The demo dates are **synthetic**;
replace them with the official calendar before real use.

### Help-desk categories

```yaml
helpdesk:
  categories:
    - key: "examinations"           # stored on the ticket
      label: "Examinations & Results"
      routed_to: "Examination Cell"   # owning office shown to students and staff
      keywords: [exam, result, revaluation]   # offline fallback classifier
      quick_questions:
        - "What is the process for applying for re-evaluation?"
```

Keep a `general` category: it is the fallback when nothing matches. The AI
classifier may only choose keys listed here — an invented category is rejected
and the keyword classifier is used instead.

---

## Applying changes

`institution.yaml` is mounted read-only into the backend, worker and beat
containers, so no rebuild is needed:

```bash
docker compose restart backend celery_worker celery_beat
```

Verify with `GET /api/v1/institution` and by logging in as a seeded member.

---

## Going deeper

| Want to customize… | Where |
|---|---|
| Meeting / procedure extraction prompts | `backend/app/services/extraction_service.py` (`_MEETING_*`, `_SKILL_*`) |
| Ticket triage prompt / urgency words | `backend/app/services/ticket_service.py` |
| Assistant answering rules | `backend/app/services/rag_service.py` |
| A new ingestion source | a `backend/app/services/connectors/*.py` subclass + `registry.py` |
| Colours | `frontend/src/app/globals.css` |
| Role display names | `frontend/src/lib/roles.ts` |
| LLM model | `LLM_MODEL` in `.env` / `backend/app/core/config.py` |

## How it works

- [`core/institution_config.py`](../backend/app/core/institution_config.py) — loads and validates the file (cached); safe defaults if missing.
- [`core/config.py`](../backend/app/core/config.py) — applies `settings` onto the app settings.
- [`services/institution_seed.py`](../backend/app/services/institution_seed.py) — seeds Users, staff Employees and reporting links in the FastAPI lifespan.
- [`api/v1/institution.py`](../backend/app/api/v1/institution.py) — public branding, read by `frontend/src/lib/useInstitution.ts`.
