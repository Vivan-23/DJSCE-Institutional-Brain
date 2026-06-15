"""
Seed the company's org structure from company.yaml on startup.

Idempotent and matched by email: editing company.yaml and restarting updates the
DB to match. People with a ``password`` get a login User (with their ``role``);
everyone becomes an Employee (so the org chart is complete even for people who
don't log in yet). Manager relationships are linked in a second pass.

Removing someone from company.yaml does NOT delete them — deactivation/removal is
a deliberate manual action, never a silent side effect of a config edit.
"""
import json
from typing import Optional

import structlog
from sqlmodel import Session, select

from app.api.v1.auth import hash_password
from app.core.company_config import get_company_config
from app.models.structured import Employee, User

log = structlog.get_logger()


def _employee_by_email(db: Session, email: str) -> Optional[Employee]:
    email = email.lower()
    for emp in db.exec(select(Employee)):
        try:
            aliases = json.loads(emp.aliases or "[]")
        except json.JSONDecodeError:
            aliases = []
        if email in [a.lower() for a in aliases]:
            return emp
    return None


def seed_company(db: Session) -> dict:
    cfg = get_company_config()
    users_created = 0
    employees_created = 0
    by_email: dict[str, Employee] = {}

    # Pass 1: upsert Users (for those with a login) and Employees.
    for ce in cfg.employees:
        user = db.exec(select(User).where(User.email == ce.email)).first()
        if ce.password and not user:
            user = User(
                email=ce.email,
                full_name=ce.name,
                hashed_password=hash_password(ce.password),
                role=ce.role,
            )
            db.add(user)
            db.commit()
            db.refresh(user)
            users_created += 1
        elif user and user.role != ce.role:
            user.role = ce.role  # keep role in sync with the profile
            db.add(user)
            db.commit()

        emp = None
        if user:
            emp = db.exec(select(Employee).where(Employee.user_id == user.id)).first()
        if not emp:
            emp = _employee_by_email(db, ce.email)
        if not emp:
            emp = Employee(display_name=ce.name, timezone=ce.timezone)
            employees_created += 1

        emp.display_name = ce.name
        emp.timezone = ce.timezone
        if user:
            emp.user_id = user.id
        aliases = set()
        try:
            aliases = set(json.loads(emp.aliases or "[]"))
        except json.JSONDecodeError:
            pass
        aliases.add(ce.email)
        emp.aliases = json.dumps(sorted(aliases))
        db.add(emp)
        db.commit()
        db.refresh(emp)
        by_email[ce.email] = emp

    # Pass 2: link managers (now that every employee row exists).
    for ce in cfg.employees:
        if not ce.manager:
            continue
        emp = by_email.get(ce.email)
        manager = by_email.get(ce.manager) or _employee_by_email(db, ce.manager)
        if emp and manager and emp.manager_id != manager.id:
            emp.manager_id = manager.id
            db.add(emp)
    db.commit()

    log.info(
        "Company profile seeded",
        company=cfg.name,
        users_created=users_created,
        employees_created=employees_created,
    )
    return {"users_created": users_created, "employees_created": employees_created}
