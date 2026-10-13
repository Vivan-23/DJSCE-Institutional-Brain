"""
Notices: staff address a message to users chosen by filters.

Audience filters (all optional; an empty list means "any"):
  roles (default: students only), departments, years, semesters, divisions.
Filters combine with AND across kinds and OR within a kind, e.g.
  {"departments": ["CE"], "years": [3, 4]}  →  CE students in third or fourth year.

Sending rules: faculty may only address their own department (enforced, not trusted
from the request); coordinators and administrators may address any department.
Recipients are resolved once, at send time, and stored, so read counts are exact and
people who join later don't receive old notices. Every send is audited.
"""
import json
from datetime import datetime, timezone
from typing import Any, Optional

from sqlmodel import Session, select

from app.core.institution_config import VALID_ROLES, get_institution_config
from app.models.structured import Notice, NoticeRecipient, User
from app.services.audit_service import audit_service

PRIORITIES = ("normal", "urgent")
_RANK = {"student": 0, "employee": 1, "manager": 2, "admin": 3}


class NoticeError(ValueError):
    """A rejected notice; the message is safe to show to the sender."""


def _aware(dt: Optional[datetime]) -> Optional[datetime]:
    return dt.replace(tzinfo=timezone.utc) if dt and not dt.tzinfo else dt


class NoticeService:
    def normalize_audience(self, sender: User, raw: dict[str, Any]) -> dict[str, list]:
        cfg = get_institution_config()
        roles = [str(r).lower() for r in raw.get("roles") or ["student"]]
        if any(r not in VALID_ROLES for r in roles):
            raise NoticeError(f"Unknown role in audience. Allowed: {', '.join(VALID_ROLES)}")
        departments = []
        for d in raw.get("departments") or []:
            code = cfg.department_code(str(d))
            if not code:
                raise NoticeError(f"Unknown department '{d}'")
            departments.append(code)
        try:
            years = sorted({int(y) for y in raw.get("years") or []})
            semesters = sorted({int(s) for s in raw.get("semesters") or []})
        except (TypeError, ValueError):
            raise NoticeError("Years and semesters must be numbers")
        if any(not 1 <= y <= 4 for y in years) or any(not 1 <= s <= 8 for s in semesters):
            raise NoticeError("Years must be 1-4 and semesters 1-8")
        divisions = sorted({str(d).strip().upper() for d in raw.get("divisions") or [] if str(d).strip()})

        if _RANK.get(sender.role, -1) < _RANK["manager"]:  # faculty: own department only
            if not sender.department:
                raise NoticeError("Your account has no department, so you cannot send notices. Ask an administrator.")
            if departments and departments != [sender.department]:
                raise NoticeError("Faculty can only send notices to their own department")
            departments = [sender.department]
        return {"roles": sorted(set(roles)), "departments": sorted(set(departments)),
                "years": years, "semesters": semesters, "divisions": divisions}

    def recipients(self, db: Session, audience: dict[str, list]) -> list[User]:
        stmt = select(User).where(User.is_active == True, User.role.in_(audience["roles"]))  # noqa: E712
        if audience["departments"]:
            stmt = stmt.where(User.department.in_(audience["departments"]))
        if audience["years"]:
            stmt = stmt.where(User.year.in_(audience["years"]))
        if audience["semesters"]:
            stmt = stmt.where(User.semester.in_(audience["semesters"]))
        if audience["divisions"]:
            stmt = stmt.where(User.division.in_(audience["divisions"]))
        return list(db.exec(stmt))

    def preview(self, db: Session, sender: User, raw: dict[str, Any]) -> dict[str, Any]:
        audience = self.normalize_audience(sender, raw)
        return {"audience": audience, "count": len(self.recipients(db, audience))}

    def send(
        self, db: Session, sender: User, *, title: str, body: str, audience: dict[str, Any],
        priority: str = "normal", expires_at: Optional[datetime] = None,
    ) -> tuple[Notice, int]:
        if not title.strip() or not body.strip():
            raise NoticeError("A notice needs a title and a message")
        if priority not in PRIORITIES:
            raise NoticeError("Priority must be normal or urgent")
        if expires_at and _aware(expires_at) <= datetime.now(timezone.utc):
            raise NoticeError("The expiry date must be in the future")
        aud = self.normalize_audience(sender, audience)
        users = self.recipients(db, aud)
        if not users:
            raise NoticeError("No one matches this audience")
        notice = Notice(sender_user_id=sender.id, title=title.strip(), body=body.strip(), priority=priority,
                        audience=json.dumps(aud), expires_at=expires_at)
        db.add(notice)
        db.commit()
        db.refresh(notice)
        for u in users:
            db.add(NoticeRecipient(notice_id=notice.id, user_id=u.id))
        db.commit()
        audit_service.record(db, actor=sender.email, action="notice_send", target_id=str(notice.id),
                             metadata={"title": notice.title, "audience": aud, "recipients": len(users)})
        return notice, len(users)

    # ── reading ─────────────────────────────────────────────────────────────
    def _serialize(self, db: Session, n: Notice, **extra: Any) -> dict[str, Any]:
        sender = db.get(User, n.sender_user_id)
        return {
            "id": str(n.id), "title": n.title, "body": n.body, "priority": n.priority,
            "audience": json.loads(n.audience or "{}"), "created_at": n.created_at.isoformat(),
            "expires_at": n.expires_at.isoformat() if n.expires_at else None,
            "sender": (sender.full_name or sender.email) if sender else None, **extra,
        }

    def inbox(self, db: Session, user: User) -> list[dict[str, Any]]:
        now = datetime.now(timezone.utc)
        rows = db.exec(select(NoticeRecipient).where(NoticeRecipient.user_id == user.id)).all()
        out = []
        for r in rows:
            n = db.get(Notice, r.notice_id)
            if not n or (n.expires_at and _aware(n.expires_at) < now):
                continue
            out.append(self._serialize(db, n, read=r.read_at is not None))
        # Newest first, then (stable sort) unread before read and urgent before normal.
        out.sort(key=lambda x: x["created_at"], reverse=True)
        out.sort(key=lambda x: (x["read"], x["priority"] != "urgent"))
        return out

    def unread_count(self, db: Session, user: User) -> int:
        return sum(1 for n in self.inbox(db, user) if not n["read"])

    def mark_read(self, db: Session, user: User, notice_id) -> bool:
        r = db.exec(select(NoticeRecipient).where(
            NoticeRecipient.user_id == user.id, NoticeRecipient.notice_id == notice_id)).first()
        if not r:
            return False
        if r.read_at is None:
            r.read_at = datetime.now(timezone.utc)
            db.add(r)
            db.commit()
        return True

    def sent(self, db: Session, user: User) -> list[dict[str, Any]]:
        """Faculty see what they sent; coordinators and administrators see every notice."""
        stmt = select(Notice).order_by(Notice.created_at.desc())
        if _RANK.get(user.role, -1) < _RANK["manager"]:
            stmt = stmt.where(Notice.sender_user_id == user.id)
        out = []
        for n in db.exec(stmt):
            recs = db.exec(select(NoticeRecipient).where(NoticeRecipient.notice_id == n.id)).all()
            out.append(self._serialize(db, n, recipients=len(recs), read=sum(r.read_at is not None for r in recs)))
        return out


notice_service = NoticeService()
