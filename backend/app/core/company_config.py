"""
Company profile loader — the single source of truth for per-company customization.

Reads ``company.yaml`` (repo root, or ``$COMPANY_CONFIG``) into typed objects.
Branding + settings + org structure all flow from here:
  - ``app.api.v1.company`` serves branding to the frontend,
  - ``app.services.company_seed`` seeds employees/users on startup,
  - ``app.core.config`` applies the settings overrides.

Dependency-light and import-safe: this module imports nothing from the app, so
``config.py`` can apply overrides without a circular import. Missing/invalid file
falls back to the built-in defaults (the demo company), so the app always boots.
"""
import functools
import os
from dataclasses import dataclass, field
from typing import Optional

import structlog
import yaml

log = structlog.get_logger()


@dataclass
class CompanyEmployee:
    name: str
    email: str
    role: str = "employee"
    title: Optional[str] = None
    manager: Optional[str] = None  # manager's email
    timezone: str = "UTC"
    password: Optional[str] = None  # set → a login User is created with `role`


@dataclass
class CompanyConfig:
    name: str = "Company Brain"
    short_code: str = "CB"
    email_domain: str = "companybrain.ai"
    pa_checkin_hour: int = 17
    commitment_followup_hours: int = 48
    employees: list[CompanyEmployee] = field(default_factory=list)


def _candidate_paths() -> list[str]:
    here = os.path.dirname(os.path.abspath(__file__))  # backend/app/core
    repo_root = os.path.abspath(os.path.join(here, "..", "..", ".."))
    return [
        os.environ.get("COMPANY_CONFIG", ""),
        os.path.join(os.getcwd(), "company.yaml"),
        os.path.join(repo_root, "company.yaml"),
        "/app/company.yaml",  # docker mount target
    ]


def _resolve_path() -> Optional[str]:
    for p in _candidate_paths():
        if p and os.path.isfile(p):
            return p
    return None


@functools.lru_cache(maxsize=1)
def get_company_config() -> CompanyConfig:
    path = _resolve_path()
    if not path:
        log.info("No company.yaml found — using default company profile")
        return CompanyConfig()
    try:
        with open(path, "r", encoding="utf-8") as f:
            raw = yaml.safe_load(f) or {}
    except Exception as e:  # noqa: BLE001 - never let a bad profile break boot
        log.error("Failed to read company.yaml — using defaults", path=path, error=str(e))
        return CompanyConfig()

    company = raw.get("company") or {}
    settings_block = raw.get("settings") or {}
    employees_raw = raw.get("employees") or []

    employees: list[CompanyEmployee] = []
    for e in employees_raw:
        if not isinstance(e, dict) or not e.get("email") or not e.get("name"):
            continue
        employees.append(
            CompanyEmployee(
                name=str(e["name"]).strip(),
                email=str(e["email"]).strip().lower(),
                role=str(e.get("role") or "employee").strip().lower(),
                title=(str(e["title"]).strip() if e.get("title") else None),
                manager=(str(e["manager"]).strip().lower() if e.get("manager") else None),
                timezone=str(e.get("timezone") or "UTC").strip(),
                password=(str(e["password"]) if e.get("password") else None),
            )
        )

    cfg = CompanyConfig(
        name=str(company.get("name") or "Company Brain").strip(),
        short_code=str(company.get("short_code") or "CB").strip(),
        email_domain=str(company.get("email_domain") or "companybrain.ai").strip(),
        pa_checkin_hour=int(settings_block.get("pa_checkin_hour", 17)),
        commitment_followup_hours=int(settings_block.get("commitment_followup_hours", 48)),
        employees=employees,
    )
    log.info("Company profile loaded", path=path, company=cfg.name, employees=len(cfg.employees))
    return cfg
