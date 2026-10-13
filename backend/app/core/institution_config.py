"""
Institution profile loader — the single source of truth for per-institution customization.

Reads ``institution.yaml`` (repo root, or ``$INSTITUTION_CONFIG``) into typed objects.
Branding, settings, help-desk routing and the people roster all flow from here:
  - ``app.api.v1.institution`` serves branding to the frontend,
  - ``app.services.institution_seed`` seeds members/users on startup,
  - ``app.services.ticket_service`` routes help-desk tickets by category,
  - ``app.core.config`` applies the settings overrides.

Dependency-light and import-safe: this module imports nothing from the app, so
``config.py`` can apply overrides without a circular import. A missing/invalid file
falls back to built-in defaults, so the app always boots.
"""
import functools
import os
from dataclasses import dataclass, field
from datetime import date
from typing import Optional

import structlog
import yaml

log = structlog.get_logger()

VALID_ROLES = ("student", "employee", "manager", "admin")


@dataclass
class InstitutionMember:
    name: str
    email: str
    role: str = "employee"  # student | employee (faculty) | manager (coordinator) | admin
    title: Optional[str] = None
    department: Optional[str] = None
    manager: Optional[str] = None  # reporting coordinator's email
    timezone: str = "Asia/Kolkata"
    password: Optional[str] = None  # set → a login User is created with `role`


@dataclass
class Department:
    code: str  # short code stored on users, fragments and meetings, e.g. "CE"
    name: str


#: Department code meaning "institution-wide": visible to every department.
ALL_DEPARTMENTS = "all"


CALENDAR_AUDIENCES = ("all", "students", "staff")


@dataclass
class CalendarEvent:
    """A published academic date (term, exam, holiday, deadline) from ``academic_calendar:``."""
    start: date
    title: str
    kind: str = "event"  # term | exam | holiday | deadline | event
    end: Optional[date] = None
    audience: str = "all"  # all | students | staff
    department: str = ALL_DEPARTMENTS


@dataclass
class HelpdeskCategory:
    key: str
    label: str
    routed_to: str  # committee / office that owns tickets in this category
    keywords: list[str] = field(default_factory=list)
    quick_questions: list[str] = field(default_factory=list)


@dataclass
class InstitutionConfig:
    name: str = "DJSCE Institutional Brain"
    short_code: str = "DJSCE"
    full_name: str = "Dwarkadas J. Sanghvi College of Engineering"
    email_domain: str = "example.com"
    pa_checkin_hour: int = 17
    commitment_followup_hours: int = 48
    helpdesk_categories: list[HelpdeskCategory] = field(default_factory=list)
    members: list[InstitutionMember] = field(default_factory=list)
    departments: list[Department] = field(default_factory=list)
    calendar: list[CalendarEvent] = field(default_factory=list)
    calendar_note: str = ""

    def department_code(self, value: Optional[str]) -> Optional[str]:
        """Resolve a department code or full name (case-insensitive) to its code, else None."""
        if not value:
            return None
        v = value.strip().lower()
        for d in self.departments:
            if v in (d.code.lower(), d.name.lower()):
                return d.code
        return None


def _candidate_paths() -> list[str]:
    here = os.path.dirname(os.path.abspath(__file__))  # backend/app/core
    repo_root = os.path.abspath(os.path.join(here, "..", "..", ".."))
    return [
        os.environ.get("INSTITUTION_CONFIG", ""),
        os.path.join(os.getcwd(), "institution.yaml"),
        os.path.join(repo_root, "institution.yaml"),
        "/app/institution.yaml",  # docker mount target
    ]


def _resolve_path() -> Optional[str]:
    for p in _candidate_paths():
        if p and os.path.isfile(p):
            return p
    return None


def _str_list(raw) -> list[str]:
    return [str(x).strip() for x in (raw or []) if str(x).strip()]


@functools.lru_cache(maxsize=1)
def get_institution_config() -> InstitutionConfig:
    path = _resolve_path()
    if not path:
        log.info("No institution.yaml found — using default profile")
        return InstitutionConfig()
    try:
        with open(path, "r", encoding="utf-8") as f:
            raw = yaml.safe_load(f) or {}
    except Exception as e:  # noqa: BLE001 - never let a bad profile break boot
        log.error("Failed to read institution.yaml — using defaults", path=path, error=str(e))
        return InstitutionConfig()

    inst = raw.get("institution") or {}
    settings_block = raw.get("settings") or {}
    defaults = InstitutionConfig()

    members: list[InstitutionMember] = []
    for m in raw.get("members") or []:
        if not isinstance(m, dict) or not m.get("email") or not m.get("name"):
            continue
        role = str(m.get("role") or "employee").strip().lower()
        if role not in VALID_ROLES:
            log.warning("Unknown role in institution.yaml — skipping member", email=m.get("email"), role=role)
            continue
        members.append(
            InstitutionMember(
                name=str(m["name"]).strip(),
                email=str(m["email"]).strip().lower(),
                role=role,
                title=(str(m["title"]).strip() if m.get("title") else None),
                department=(str(m["department"]).strip() if m.get("department") else None),
                manager=(str(m["manager"]).strip().lower() if m.get("manager") else None),
                timezone=str(m.get("timezone") or "Asia/Kolkata").strip(),
                password=(str(m["password"]) if m.get("password") else None),
            )
        )

    departments = [
        Department(code=str(d["code"]).strip(), name=str(d.get("name") or d["code"]).strip())
        for d in raw.get("departments") or []
        if isinstance(d, dict) and d.get("code")
    ]

    cal_block = raw.get("academic_calendar") or {}
    calendar: list[CalendarEvent] = []
    for e in cal_block.get("events") or []:
        try:
            start = date.fromisoformat(str(e["date"]))
            end = date.fromisoformat(str(e["end"])) if e.get("end") else None
        except (KeyError, TypeError, ValueError):
            log.warning("Skipping calendar event with a bad date", entry=e)
            continue
        audience = str(e.get("audience") or "all").strip().lower()
        if audience not in CALENDAR_AUDIENCES or not e.get("title"):
            log.warning("Skipping calendar event with bad audience/title", entry=e)
            continue
        calendar.append(CalendarEvent(
            start=start, end=end, title=str(e["title"]).strip(), kind=str(e.get("kind") or "event").strip().lower(),
            audience=audience, department=str(e.get("department") or ALL_DEPARTMENTS).strip(),
        ))
    calendar.sort(key=lambda ev: ev.start)

    categories: list[HelpdeskCategory] = []
    for c in (raw.get("helpdesk") or {}).get("categories") or []:
        if not isinstance(c, dict) or not c.get("key"):
            continue
        categories.append(
            HelpdeskCategory(
                key=str(c["key"]).strip().lower(),
                label=str(c.get("label") or c["key"]).strip(),
                routed_to=str(c.get("routed_to") or "Help Desk").strip(),
                keywords=[k.lower() for k in _str_list(c.get("keywords"))],
                quick_questions=_str_list(c.get("quick_questions")),
            )
        )

    cfg = InstitutionConfig(
        name=str(inst.get("name") or defaults.name).strip(),
        short_code=str(inst.get("short_code") or defaults.short_code).strip(),
        full_name=str(inst.get("full_name") or defaults.full_name).strip(),
        email_domain=str(inst.get("email_domain") or defaults.email_domain).strip(),
        pa_checkin_hour=int(settings_block.get("pa_checkin_hour", 17)),
        commitment_followup_hours=int(settings_block.get("commitment_followup_hours", 48)),
        helpdesk_categories=categories,
        members=members,
        departments=departments,
        calendar=calendar,
        calendar_note=str(cal_block.get("note") or "").strip(),
    )
    # Members may name a department by code or full name; store the code. A profile with
    # no `departments:` list keeps the free-text value (department scoping then unused).
    for m in cfg.members:
        if m.department and cfg.departments:
            code = cfg.department_code(m.department)
            if not code:
                log.warning("Unknown department in institution.yaml", email=m.email, department=m.department)
            m.department = code
    log.info("Institution profile loaded", path=path, institution=cfg.name, members=len(cfg.members))
    return cfg
