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
    )
    log.info("Institution profile loaded", path=path, institution=cfg.name, members=len(cfg.members))
    return cfg
