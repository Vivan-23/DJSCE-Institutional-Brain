"""
Commitment service.

Commitments (action items) are first-class: created from meeting extraction and
from PA conversations, tracked through a status lifecycle, and surfaced to the PA
when they need a follow-up.
"""
from datetime import datetime, timedelta, timezone
from typing import Optional
from uuid import UUID

import structlog
from sqlmodel import Session, select

from app.core.config import settings
from app.models.structured import Commitment, CommitmentUpdate, Meeting
from app.services.date_parser import parse_due_date
from app.services.employee_service import employee_service

log = structlog.get_logger()

VALID_STATUSES = {"open", "in_progress", "blocked", "done", "dropped"}
_OPEN_STATUSES = {"open", "in_progress", "blocked"}


class CommitmentService:
    def create_from_meeting(
        self, db: Session, meeting: Meeting, commitments: list[dict]
    ) -> list[Commitment]:
        """Persist commitments extracted from a meeting, resolving assignees to employees."""
        created: list[Commitment] = []
        for item in commitments:
            description = (item.get("description") or "").strip()
            if not description:
                continue
            assignee_name = item.get("assignee")
            employee = (
                employee_service.resolve_or_create(db, assignee_name)
                if assignee_name
                else None
            )
            commitment = Commitment(
                assignee_employee_id=employee.id if employee else None,
                description=description,
                source_meeting_id=meeting.id,
                due_date=parse_due_date(item.get("due")),
                status="open",
                confidence=float(item.get("confidence", 0.7)),
            )
            db.add(commitment)
            created.append(commitment)
        if created:
            db.commit()
            for c in created:
                db.refresh(c)
            log.info("Commitments created from meeting", meeting_id=str(meeting.id), count=len(created))
        return created

    def list_all(self, db: Session, *, status: Optional[str] = None) -> list[Commitment]:
        stmt = select(Commitment).order_by(Commitment.created_at.desc())
        if status:
            stmt = stmt.where(Commitment.status == status)
        return list(db.exec(stmt))

    def for_employee(
        self, db: Session, employee_id: UUID, *, open_only: bool = False
    ) -> list[Commitment]:
        stmt = select(Commitment).where(Commitment.assignee_employee_id == employee_id)
        if open_only:
            stmt = stmt.where(Commitment.status.in_(_OPEN_STATUSES))  # type: ignore[attr-defined]
        return list(db.exec(stmt.order_by(Commitment.created_at.desc())))

    def update_status(
        self, db: Session, commitment_id: UUID, status: str
    ) -> Optional[Commitment]:
        if status not in VALID_STATUSES:
            raise ValueError(f"Invalid status '{status}'. Allowed: {sorted(VALID_STATUSES)}")
        commitment = db.get(Commitment, commitment_id)
        if not commitment:
            return None
        commitment.status = status
        db.add(commitment)
        db.commit()
        db.refresh(commitment)
        return commitment

    def record_update(
        self,
        db: Session,
        commitment_id: UUID,
        *,
        raw_text: str,
        structured_summary: Optional[str] = None,
        status_change: Optional[str] = None,
        source: str = "checkin",
    ) -> Optional[CommitmentUpdate]:
        """Log an update in the employee's own words; apply a status change if given."""
        commitment = db.get(Commitment, commitment_id)
        if not commitment:
            return None
        update = CommitmentUpdate(
            commitment_id=commitment_id,
            raw_text=raw_text,
            structured_summary=structured_summary,
            status_change=status_change,
            source=source,
        )
        db.add(update)
        if status_change and status_change in VALID_STATUSES:
            commitment.status = status_change
        commitment.last_followup_at = datetime.now(timezone.utc)
        db.add(commitment)
        db.commit()
        db.refresh(update)
        return update

    def needs_followup(self, db: Session) -> list[Commitment]:
        """Open commitments with no recent update/follow-up — eligible for a PA nudge."""
        cutoff = datetime.now(timezone.utc) - timedelta(hours=settings.COMMITMENT_FOLLOWUP_HOURS)
        result: list[Commitment] = []
        for c in db.exec(select(Commitment).where(Commitment.status.in_(_OPEN_STATUSES))):  # type: ignore[attr-defined]
            last = c.last_followup_at or c.created_at
            if last.tzinfo is None:
                last = last.replace(tzinfo=timezone.utc)
            if last <= cutoff:
                result.append(c)
        return result


commitment_service = CommitmentService()
