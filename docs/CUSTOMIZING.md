# Customizing Company Brain for a company

Company Brain is built to be **forked per company** from the `template` branch.
For most customization you edit **one file — [`company.yaml`](../company.yaml)** —
and the system reconfigures itself on restart. Last verified: 2026-06-15.

---

## The one file: `company.yaml`

`company.yaml` (repo root) is the single source of truth for a company's profile.
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
  name: "Acme Corp"
  short_code: "AC"
  email_domain: "acme.com"

settings:
  pa_checkin_hour: 17
  commitment_followup_hours: 48

employees:
  - name: "Dana Lee"
    email: "dana@acme.com"
    role: "admin"            # employee | manager | admin
    title: "VP Engineering"
    manager: null
    timezone: "America/New_York"
    password: "changeme123"  # set → this person gets a login
  - name: "Ravi Patel"
    email: "ravi@acme.com"
    role: "manager"
    manager: "dana@acme.com"
    timezone: "America/New_York"
    password: "changeme123"
  - name: "Maya Chen"        # no password → in the org chart, no login yet
    email: "maya@acme.com"
    role: "employee"
    manager: "ravi@acme.com"
    timezone: "Asia/Kolkata"
```

- People with a `password` get a **login User** with their `role`; everyone
  becomes an **Employee** (so the org chart is complete even for non-users).
- `manager` is the manager's **email**; links resolve after all rows are created.
- `role` controls access: `employee < manager < admin` (managers can review/
  approve skills, run extraction, sync sources, read the audit log).

---

## The agent-driven workflow

This is designed so you can **describe the company in a prompt** and have the
agent fill in the profile:

1. **Fork** the `template` branch for the company.
2. Tell the agent the company details (people, reporting lines, timezones, name,
   check-in time, any company-specific rules).
3. The agent rewrites **`company.yaml`** to match — usually nothing else is needed
   for org + branding customization.
4. `docker compose up -d --build` (or just restart the backend if only
   `company.yaml` changed — it's mounted as a live volume, no rebuild needed).
5. Verify: `GET /api/v1/company` shows the new branding; log in as the seeded
   admin; the org structure is in place.

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

Keep company-specific code changes on the company's fork; fold any
**generally useful** improvements back into `main`/`template`.

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
