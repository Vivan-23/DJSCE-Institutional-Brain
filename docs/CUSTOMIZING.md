# Customizing the institutional profile

The platform is configured for DJSCE through a single profile file.
For most customization you edit **one file — [`company.yaml`](../company.yaml)** —
and the system reconfigures itself on restart. Last verified: 2026-10-13.

---

## The one file: `company.yaml`

`company.yaml` (repo root) is the single source of truth for the institution's profile (the filename is kept from the original Company-Brain codebase).
On startup the backend reads it and:

| Section | Drives | Where it shows up |
|---|---|---|
| `company.name` / `short_code` | UI branding (header + logo badge, login page) | `GET /api/v1/company` → Sidebar & Login |
| `company.email_domain` | default domain for derived/internal emails | extraction / employee stubs |
| `settings.pa_checkin_hour` | end-of-day PA check-in time | Celery beat schedule |
| `settings.commitment_followup_hours` | when a commitment is "stale" | follow-up scans |
| `employees[]` | the org structure (people, roles, managers, timezones) | seeded into the DB |

It is **idempotent** (matched by email): edit it, restart, and the DB updates to
match. Removing a person from the file does **not** delete them — that stays a
deliberate manual action.

### Example

```yaml
company:
  name: "DJSCE Institutional Brain"
  short_code: "DJSCE"
  email_domain: "example.com"

settings:
  pa_checkin_hour: 17
  commitment_followup_hours: 48

employees:
  - name: "Demo Administrator"
    email: "demo@example.com"
    role: "admin"            # employee | manager | admin
    title: "Institutional Platform Administrator"
    manager: null
    timezone: "Asia/Kolkata"
    password: "demo123"      # set → this person gets a login
  - name: "Dr. Aditi Rao"    # synthetic person
    email: "aditi.rao@example.com"
    role: "manager"          # e.g. a committee coordinator
    manager: "demo@example.com"
    timezone: "Asia/Kolkata"
  - name: "Prof. Karan Shah" # no password → appears in the org, no login
    email: "karan.shah@example.com"
    role: "employee"
    manager: "aditi.rao@example.com"
    timezone: "Asia/Kolkata"
```

- People with a `password` get a **login User** with their `role`; everyone
  becomes an **Employee** (so the org chart is complete even for non-users).
- `manager` is the manager's **email**; links resolve after all rows are created.
- `role` controls access: `employee < manager < admin` (managers can review/
  approve skills, run extraction, sync sources, read the audit log).

---

## Updating the profile

1. Edit **`company.yaml`** — people, reporting lines, roles, name, check-in time.
2. Restart the backend containers (no rebuild needed — the file is mounted).
3. Verify: `GET /api/v1/company` shows the branding; log in as the seeded
   admin; the people are in place.

> Because `company.yaml` is mounted into the containers
> (`./company.yaml:/app/company.yaml:ro`), editing it + `docker compose restart
> backend celery_worker celery_beat` applies changes **without a rebuild**.

---

## Going deeper (when one file isn't enough)

`company.yaml` covers org structure, branding, and settings. For company-specific
*behavior*, these are the natural extension points (see
[ARCHITECTURE.md](ARCHITECTURE.md) for the map):

| Want to customize… | Where |
|---|---|
| Skill extraction prompts / domains | `backend/app/services/extraction_service.py` (`_SKILL_*`, `_MEETING_*`) |
| A new ingestion source (Slack/Jira/etc.) | add a `backend/app/services/connectors/*.py` + register in `registry.py` |
| Branding beyond name/logo (colors) | `frontend/src/app/globals.css` (`--color-primary`, …) |
| Default skills/playbooks to ship | seed `Skill` rows (extend `company_seed.py`) |
| LLM model | `LLM_MODEL` in `.env` / `backend/app/core/config.py` |


---

## How it works (for maintainers)

- **[`backend/app/core/company_config.py`](../backend/app/core/company_config.py)** —
  loads/validates `company.yaml` (cached); falls back to safe defaults if missing.
- **[`backend/app/core/config.py`](../backend/app/core/config.py)** — applies the
  `settings` overrides onto the app settings.
- **[`backend/app/services/company_seed.py`](../backend/app/services/company_seed.py)** —
  idempotent seeding of Users + Employees + manager links; runs in the FastAPI
  lifespan on startup.
- **[`backend/app/api/v1/company.py`](../backend/app/api/v1/company.py)** —
  `GET /api/v1/company` serves branding; the frontend reads it via
  `frontend/src/lib/useCompany.ts`.
