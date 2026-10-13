"""
Academic calendar and deadline reminders.

Two sources, merged into one dated list per user:
  - published academic dates (``academic_calendar:`` in institution.yaml), filtered by
    audience (students / staff / all) and the user's department scope;
  - for staff, their own open commitments that have a due date.

Reminders are computed on read (no table): each item carries ``days_left`` and an
``urgency`` (overdue / today / soon / upcoming). A daily beat task also posts staff
reminders for anything due within ``SOON_DAYS`` to the Active Feed.
"""
from datetime import date, datetime, timedelta, timezone
from typing import Any, Optional

import structlog
from sqlmodel import Session, select

from app.core.institution_config import ALL_DEPARTMENTS, get_institution_config
from app.models.structured import ActiveInsight, Commitment, Employee, Meeting, User

log = structlog.get_logger()

SOON_DAYS = 3
_OPEN = ("open", "in_progress", "blocked")


def _urgency(days_left: int) -> str:
    if days_left < 0:
        return "overdue"
    if days_left == 0:
        return "today"
    return "soon" if days_left <= SOON_DAYS else "upcoming"


class CalendarService:
    def events_for(
        self, *, staff: bool, departments: Optional[list[str]], today: date, days: int
    ) -> list[dict[str, Any]]:
        """Published academic dates visible to this audience, from ``today`` to ``today + days``."""
        horizon = today + timedelta(days=days)
        audiences = {"all", "staff"} if staff else {"all", "students"}
        out = []
        for ev in get_institution_config().calendar:
            last = ev.end or ev.start
            if ev.audience not in audiences or last < today or ev.start > horizon:
                continue
            if departments is not None and ev.department not in departments:
                continue
            # A multi-day event that has already started is "today" until it ends.
            days_left = max((ev.start - today).days, 0)
            out.append({
                "date": ev.start.isoformat(),
                "end": ev.end.isoformat() if ev.end else None,
                "title": ev.title,
                "kind": ev.kind,
                "audience": ev.audience,
                "department": ev.department,
                "source": "calendar",
                "days_left": days_left,
                "urgency": _urgency(days_left),
            })
        return out

    def commitments_for(self, db: Session, user: User, *, today: date, days: int) -> list[dict[str, Any]]:
        """The user's own open commitments due by ``today + days`` (overdue ones included)."""
        emp = db.exec(select(Employee).where(Employee.user_id == user.id)).first()
        if not emp:
            return []
        horizon = today + timedelta(days=days)
        rows = db.exec(
            select(Commitment).where(
                Commitment.assignee_employee_id == emp.id,
                Commitment.status.in_(_OPEN),
                Commitment.due_date.is_not(None),
            )
        ).all()
        out = []
        for c in rows:
            due = c.due_date.date()
            if due > horizon:
                continue
            meeting = db.get(Meeting, c.source_meeting_id) if c.source_meeting_id else None
            days_left = (due - today).days
            out.append({
                "date": due.isoformat(),
                "end": None,
                "title": c.description,
                "kind": "commitment",
                "audience": "staff",
                "department": meeting.department if meeting else ALL_DEPARTMENTS,
                "source": "commitment",
                "meeting": meeting.title if meeting else None,
                "commitment_id": str(c.id),
                "status": c.status,
                "days_left": days_left,
                "urgency": _urgency(days_left),
            })
        return out

    def upcoming(
        self,
        db: Session,
        user: User,
        *,
        staff: bool,
        departments: Optional[list[str]],
        days: int = 60,
        today: Optional[date] = None,
    ) -> list[dict[str, Any]]:
        today = today or datetime.now(timezone.utc).date()
        items = self.events_for(staff=staff, departments=departments, today=today, days=days)
        if staff:
            items += self.commitments_for(db, user, today=today, days=days)
        return sorted(items, key=lambda i: (i["date"], i["source"] != "calendar"))

    def post_reminders(self, db: Session, today: Optional[date] = None) -> int:
        """Daily: Active Feed reminders for staff dates and commitments due within SOON_DAYS.

        Idempotent: an identical observation is never posted twice.
        """
        today = today or datetime.now(timezone.utc).date()
        existing = {
            i.observation for i in db.exec(select(ActiveInsight).where(ActiveInsight.category == "deadline"))
        }
        due: list[tuple[str, str]] = []
        for ev in self.events_for(staff=True, departments=None, today=today, days=SOON_DAYS):
            due.append((f"{ev['title']}: {ev['date']} ({ev['urgency']})", "Published academic date."))
        open_with_due = select(Commitment).where(Commitment.status.in_(_OPEN), Commitment.due_date.is_not(None))
        for c in db.exec(open_with_due):
            days_left = (c.due_date.date() - today).days
            if days_left <= SOON_DAYS:
                due.append((
                    f"Commitment due {c.due_date.date().isoformat()} ({_urgency(days_left)}): {c.description}",
                    "An open commitment from a meeting is due soon or overdue.",
                ))
        created = 0
        for observation, why in due:
            if observation in existing:
                continue
            db.add(ActiveInsight(
                category="deadline",
                observation=observation,
                impact_rationale=why,
                suggested_actions='["Confirm the owner is on track", "Update the status after acting"]',
                confidence_score=1.0,
            ))
            existing.add(observation)
            created += 1
        db.commit()
        log.info("Deadline reminders posted", count=created)
        return created


calendar_service = CalendarService()
