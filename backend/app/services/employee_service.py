"""
Employee service — resolve the people the PA serves.

Meeting/commitment extraction yields plain names ("Priya", "Alex Chen"); these
must map to Employee rows. Login Users are also linked to an Employee so each
person can talk to their own PA.
"""
import json
from typing import Optional
from uuid import UUID

import structlog
from sqlmodel import Session, select

from app.models.structured import Employee, User

log = structlog.get_logger()


class EmployeeService:
    def resolve_or_create(self, db: Session, display_name: str) -> Optional[Employee]:
        """Match a name against existing employees (name or alias); create a stub if new."""
        name = (display_name or "").strip()
        if not name:
            return None

        candidates = db.exec(select(Employee)).all()
        lowered = name.lower()
        for emp in candidates:
            if emp.display_name.strip().lower() == lowered:
                return emp
            try:
                aliases = json.loads(emp.aliases or "[]")
            except json.JSONDecodeError:
                aliases = []
            if any(a.strip().lower() == lowered for a in aliases):
                return emp
            # First-name match against a single-token query (e.g. "Priya" -> "Priya Patel")
            if " " not in lowered and emp.display_name.lower().split()[:1] == [lowered]:
                return emp

        emp = Employee(display_name=name)
        db.add(emp)
        db.commit()
        db.refresh(emp)
        log.info("Created employee stub from extraction", name=name)
        return emp

    def get_or_create_for_user(self, db: Session, user: User) -> Employee:
        """Return the Employee linked to a login User, creating/linking if needed."""
        existing = db.exec(select(Employee).where(Employee.user_id == user.id)).first()
        if existing:
            return existing

        # Try to adopt a stub that matches the user's name before creating a new one
        emp: Optional[Employee] = None
        if user.full_name:
            emp = self.resolve_or_create(db, user.full_name)
        if emp is None:
            emp = Employee(display_name=user.full_name or user.email)
            db.add(emp)
        emp.user_id = user.id
        db.add(emp)
        db.commit()
        db.refresh(emp)
        return emp

    def list_active(self, db: Session) -> list[Employee]:
        return list(db.exec(select(Employee).where(Employee.active == True)))  # noqa: E712

    def get(self, db: Session, employee_id: UUID) -> Optional[Employee]:
        return db.get(Employee, employee_id)


employee_service = EmployeeService()
