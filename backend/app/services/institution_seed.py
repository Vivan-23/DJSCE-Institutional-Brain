"""
Seed the institution's people from institution.yaml on startup.

Idempotent and matched by email: editing institution.yaml and restarting updates
the DB to match. Members with a ``password`` get a login User (with their
``role``). Staff (everyone except students) also become an Employee row — the
person the Faculty Desk PA serves and commitments are assigned to — and their
reporting links are resolved in a second pass. Students only get a login.

Removing someone from institution.yaml does NOT delete them — deactivation/removal
is a deliberate manual action, never a silent side effect of a config edit.
"""
import json
from typing import Optional

import structlog
from sqlmodel import Session, select

from app.api.v1.auth import hash_password
from app.core.institution_config import get_institution_config
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


def seed_institution(db: Session) -> dict:
    cfg = get_institution_config()
    users_created = 0
    employees_created = 0
    by_email: dict[str, Employee] = {}

    # Pass 1: upsert Users (for those with a login) and staff Employees.
    for m in cfg.members:
        user = db.exec(select(User).where(User.email == m.email)).first()
        if m.password and not user:
            user = User(
                email=m.email,
                full_name=m.name,
                hashed_password=hash_password(m.password),
                role=m.role,
                department=m.department,
            )
            db.add(user)
            db.commit()
            db.refresh(user)
            users_created += 1
        elif user and (user.role != m.role or user.department != m.department):
            user.role = m.role  # keep role and department in sync with the profile
            user.department = m.department
            db.add(user)
            db.commit()

        if m.role == "student":
            continue

        emp = None
        if user:
            emp = db.exec(select(Employee).where(Employee.user_id == user.id)).first()
        if not emp:
            emp = _employee_by_email(db, m.email)
        if not emp:
            emp = Employee(display_name=m.name, timezone=m.timezone)
            employees_created += 1

        emp.display_name = m.name
        emp.timezone = m.timezone
        if user:
            emp.user_id = user.id
        aliases = set()
        try:
            aliases = set(json.loads(emp.aliases or "[]"))
        except json.JSONDecodeError:
            pass
        aliases.add(m.email)
        emp.aliases = json.dumps(sorted(aliases))
        db.add(emp)
        db.commit()
        db.refresh(emp)
        by_email[m.email] = emp

    # Pass 2: link reporting coordinators (now that every staff row exists).
    for m in cfg.members:
        if not m.manager or m.email not in by_email:
            continue
        emp = by_email[m.email]
        manager = by_email.get(m.manager) or _employee_by_email(db, m.manager)
        if manager and emp.manager_id != manager.id:
            emp.manager_id = manager.id
            db.add(emp)
    db.commit()

    log.info(
        "Institution profile seeded",
        institution=cfg.name,
        users_created=users_created,
        employees_created=employees_created,
    )
    return {"users_created": users_created, "employees_created": employees_created}
