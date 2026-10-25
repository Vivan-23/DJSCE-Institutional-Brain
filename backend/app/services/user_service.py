"""
Administrator user management: create, edit, deactivate, reset passwords, CSV import.

Rules enforced here (not just in the UI):
  - roles must be one of student / employee / manager / admin; departments must exist
    in institution.yaml; year 1-4 and semester 1-8 must agree (semester 2y-1 or 2y);
  - an administrator cannot demote or deactivate themselves, and the last active
    administrator cannot be demoted or deactivated;
  - staff users always get a linked Employee (the Faculty Desk PA serves Employees);
  - an email (the login) can be changed by an administrator, e.g. replacing a placeholder; it must
    stay unique, and the person's current session ends (tokens carry the old email);
  - every change is written to the audit log.
"""
import csv
import io
import secrets
from typing import Any, Optional
from uuid import UUID

from sqlmodel import Session, select

from app.core.institution_config import VALID_ROLES, get_institution_config
from app.models.structured import User
from app.services.audit_service import audit_service
from app.services.employee_service import employee_service

EDITABLE = ("full_name", "role", "department", "year", "semester", "division", "is_active")
CSV_COLUMNS = ("email", "full_name", "role", "department", "year", "semester", "division", "password")


class UserError(ValueError):
    """A rejected change; the message is safe to show to the administrator."""


def temporary_password() -> str:
    return secrets.token_urlsafe(9)


def serialize(u: User) -> dict[str, Any]:
    return {
        "id": str(u.id), "email": u.email, "full_name": u.full_name, "role": u.role,
        "department": u.department, "year": u.year, "semester": u.semester, "division": u.division,
        "is_active": u.is_active, "must_change_password": u.must_change_password, "created_at": u.created_at.isoformat(),
    }


class UserService:
    # ── validation ──────────────────────────────────────────────────────────
    @staticmethod
    def _clean(fields: dict[str, Any]) -> dict[str, Any]:
        out = {k: v for k, v in fields.items() if k in EDITABLE}
        if "role" in out:
            out["role"] = str(out["role"]).strip().lower()
            if out["role"] not in VALID_ROLES:
                raise UserError(f"Unknown role '{out['role']}'. Allowed: {', '.join(VALID_ROLES)}")
        if "department" in out:
            raw = out["department"]
            if raw in (None, ""):
                out["department"] = None
            else:
                code = get_institution_config().department_code(str(raw))
                if not code:
                    raise UserError(f"Unknown department '{raw}'")
                out["department"] = code
        for key, lo, hi in (("year", 1, 4), ("semester", 1, 8)):
            if key in out:
                v = out[key]
                if v in (None, ""):
                    out[key] = None
                    continue
                try:
                    out[key] = int(v)
                except (TypeError, ValueError):
                    raise UserError(f"{key} must be a number")
                if not lo <= out[key] <= hi:
                    raise UserError(f"{key} must be between {lo} and {hi}")
        if "division" in out:
            out["division"] = (str(out["division"]).strip().upper() or None) if out["division"] is not None else None
        if "full_name" in out and out["full_name"] is not None:
            out["full_name"] = str(out["full_name"]).strip() or None
        return out

    @staticmethod
    def _check_cohort(user: User) -> None:
        if user.year and user.semester and user.semester not in (2 * user.year - 1, 2 * user.year):
            raise UserError(f"Semester {user.semester} does not belong to year {user.year}")

    def _active_admins(self, db: Session) -> int:
        return len(db.exec(select(User).where(User.role == "admin", User.is_active == True)).all())  # noqa: E712

    def _guard(self, db: Session, actor: User, target: User, new: dict[str, Any]) -> None:
        demoting = "role" in new and new["role"] != "admin" and target.role == "admin"
        deactivating = new.get("is_active") is False and target.is_active
        if target.id == actor.id and (demoting or deactivating):
            raise UserError("You cannot remove your own administrator access")
        if (demoting or deactivating) and target.role == "admin" and self._active_admins(db) <= 1:
            raise UserError("At least one active administrator must remain")

    @staticmethod
    def _ensure_staff_profile(db: Session, user: User) -> None:
        if user.role != "student":
            employee_service.get_or_create_for_user(db, user)

    # ── queries ─────────────────────────────────────────────────────────────
    def list(
        self, db: Session, *, q: Optional[str] = None, role: Optional[str] = None,
        department: Optional[str] = None, active: Optional[bool] = None,
    ) -> list[User]:
        stmt = select(User).order_by(User.role, User.email)
        if role:
            stmt = stmt.where(User.role == role)
        if department:
            stmt = stmt.where(User.department == department)
        if active is not None:
            stmt = stmt.where(User.is_active == active)
        users = list(db.exec(stmt))
        if q:
            needle = q.strip().lower()
            users = [u for u in users if needle in u.email.lower() or needle in (u.full_name or "").lower()]
        return users

    def get(self, db: Session, user_id: str) -> Optional[User]:
        try:
            return db.get(User, UUID(user_id))
        except ValueError:
            return None

    # ── changes ─────────────────────────────────────────────────────────────
    def create(self, db: Session, actor: User, data: dict[str, Any], *, audit: bool = True) -> tuple[User, str]:
        """Create a user; returns (user, password). A temporary password is generated if none is given."""
        from app.api.v1.auth import hash_password

        email = str(data.get("email") or "").strip().lower()
        if "@" not in email:
            raise UserError("A valid email is required")
        if db.exec(select(User).where(User.email == email)).first():
            raise UserError(f"{email} already exists")
        fields = self._clean({"role": "student", **data})
        password = str(data.get("password") or "") or temporary_password()
        if len(password) < 6:
            raise UserError("Password must be at least 6 characters")
        user = User(email=email, hashed_password=hash_password(password),
                    must_change_password=not data.get("password"), **fields)
        self._check_cohort(user)
        db.add(user)
        db.commit()
        db.refresh(user)
        self._ensure_staff_profile(db, user)
        if audit:
            audit_service.record(db, actor=actor.email, action="user_create", target_id=str(user.id),
                                 metadata={"email": email, "role": user.role, "department": user.department})
        return user, password

    def update(self, db: Session, actor: User, user: User, data: dict[str, Any]) -> User:
        new = self._clean(data)
        self._guard(db, actor, user, new)
        before = {k: getattr(user, k) for k in new}
        for k, v in new.items():
            setattr(user, k, v)
        self._check_cohort(user)
        db.add(user)
        db.commit()
        db.refresh(user)
        self._ensure_staff_profile(db, user)
        changed = {k: [before[k], v] for k, v in new.items() if before[k] != v}
        if changed:
            audit_service.record(db, actor=actor.email, action="user_update", target_id=str(user.id),
                                 metadata={"email": user.email, "changes": changed})
        return user

    def change_email(self, db: Session, actor: User, user: User, email: str) -> User:
        email = (email or "").strip().lower()
        if "@" not in email or email.startswith("@") or email.endswith("@") or " " in email:
            raise UserError("A valid email is required")
        if email == user.email:
            return user
        if db.exec(select(User).where(User.email == email, User.id != user.id)).first():
            raise UserError(f"{email} already belongs to another account")
        old = user.email
        user.email = email
        db.add(user)
        db.commit()
        db.refresh(user)
        audit_service.record(db, actor=actor.email, action="user_email_changed", target_id=str(user.id),
                             metadata={"from": old, "to": email})
        return user

    def reset_password(self, db: Session, actor: User, user: User, password: Optional[str] = None) -> str:
        from app.api.v1.auth import hash_password

        generated = not password
        password = password or temporary_password()
        if len(password) < 6:
            raise UserError("Password must be at least 6 characters")
        user.hashed_password = hash_password(password)
        user.must_change_password = generated
        db.add(user)
        db.commit()
        audit_service.record(db, actor=actor.email, action="user_password_reset", target_id=str(user.id),
                             metadata={"email": user.email})
        return password

    def import_csv(self, db: Session, actor: User, content: str) -> dict[str, Any]:
        """Create users from CSV rows (header: email, full_name, role, department, year, semester,
        division, password). Existing emails are skipped; a bad row is reported, not fatal."""
        reader = csv.DictReader(io.StringIO(content.lstrip("﻿")))
        if not reader.fieldnames or "email" not in [h.strip().lower() for h in reader.fieldnames]:
            raise UserError("The CSV needs a header row with at least an 'email' column")
        created, skipped, errors = [], [], []
        for line, row in enumerate(reader, start=2):
            row = {(k or "").strip().lower(): (v or "").strip() for k, v in row.items()}
            data = {k: row[k] for k in CSV_COLUMNS if row.get(k)}
            try:
                if db.exec(select(User).where(User.email == data.get("email", "").lower())).first():
                    skipped.append(data.get("email"))
                    continue
                user, password = self.create(db, actor, data, audit=False)
                created.append({"email": user.email, "role": user.role,
                                "temporary_password": None if row.get("password") else password})
            except UserError as e:
                db.rollback()
                errors.append({"line": line, "email": data.get("email"), "error": str(e)})
        audit_service.record(db, actor=actor.email, action="user_import",
                             metadata={"created": len(created), "skipped": len(skipped), "errors": len(errors)})
        return {"created": created, "skipped": skipped, "errors": errors}


user_service = UserService()
