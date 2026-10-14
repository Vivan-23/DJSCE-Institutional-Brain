"""
Commitment service.

Commitments (action items) are first-class: created from meeting extraction and
from PA conversations, tracked through a status lifecycle, and surfaced to the PA
when they need a follow-up.
"""
import re
from datetime import datetime, timedelta, timezone
from typing import Optional
from uuid import UUID

import structlog
from sqlmodel import Session, select

from app.core.config import settings
from app.models.structured import Commitment, CommitmentUpdate, Employee, Meeting
from app.services.date_parser import parse_due_date
from app.services.employee_service import employee_service

log = structlog.get_logger()

# "review" = the owner says it's done and a coordinator has yet to confirm; "done" = confirmed.
VALID_STATUSES = {"open", "in_progress", "blocked", "review", "done", "dropped"}
_OPEN_STATUSES = {"open", "in_progress", "blocked"}
#: Statuses an owner may set on their own task (confirming "done" is a coordinator's call).
OWNER_STATUSES = {"open", "in_progress", "blocked", "review"}


class CommitmentError(ValueError):
    """A rejected change; the message is safe to show."""


class CommitmentService:
    def create_from_meeting(
        self, db: Session, meeting: Meeting, commitments: list[dict], *,
        assigned_by: Optional[str] = None, assigned_by_user_id: Optional[str] = None,
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
                department=meeting.department or "all",
                assigned_by=assigned_by,
                assigned_by_user_id=UUID(assigned_by_user_id) if assigned_by_user_id else None,
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
        progress: Optional[int] = None,
        remaining: Optional[str] = None,
        blocked_reason: Optional[str] = None,
        actor: Optional[str] = None,
    ) -> Optional[CommitmentUpdate]:
        """Log an update (the person's own words) and apply status / progress / what's-left changes.

        An owner, a follow-up reply or the check-in assistant saying a task is "done" moves it
        to ``review``: only a coordinator's confirmation makes it ``done``.
        """
        commitment = db.get(Commitment, commitment_id)
        if not commitment:
            return None
        if status_change == "done" and source != "coordinator":
            status_change = "review"
        if status_change not in VALID_STATUSES:
            status_change = None
        if progress is not None:
            progress = max(0, min(100, int(progress)))
        now = datetime.now(timezone.utc)
        update = CommitmentUpdate(
            commitment_id=commitment_id,
            raw_text=raw_text,
            structured_summary=structured_summary,
            status_change=status_change,
            progress=progress,
            actor=actor,
            source=source,
        )
        db.add(update)
        if status_change:
            commitment.status = status_change
            if status_change == "review":
                commitment.marked_done_at = now
                progress = 100 if progress is None else progress
            if status_change != "blocked":
                commitment.blocked_reason = None
        if progress is not None:
            commitment.progress = progress
            if commitment.status == "open" and progress > 0 and not status_change:
                commitment.status = "in_progress"
        if remaining is not None:
            commitment.remaining = remaining.strip() or None
        if blocked_reason and blocked_reason.strip():
            commitment.blocked_reason = blocked_reason.strip()
            if commitment.status in ("open", "in_progress"):
                commitment.status = "blocked"
        commitment.last_followup_at = now
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


    # ── coordinator actions ─────────────────────────────────────────────────
    def confirm(self, db: Session, commitment: Commitment, actor: str) -> Commitment:
        if commitment.status != "review":
            raise CommitmentError("Only a task its owner marked done can be confirmed")
        self.record_update(db, commitment.id, raw_text="Completion confirmed", status_change="done",
                           progress=100, source="coordinator", actor=actor)
        commitment = db.get(Commitment, commitment.id)
        commitment.confirmed_at = datetime.now(timezone.utc)
        commitment.confirmed_by = actor
        db.add(commitment)
        db.commit()
        db.refresh(commitment)
        return commitment

    def send_back(self, db: Session, commitment: Commitment, actor: str, comment: str) -> Commitment:
        if commitment.status != "review":
            raise CommitmentError("Only a task awaiting confirmation can be sent back")
        if not comment.strip():
            raise CommitmentError("Say what still needs doing")
        self.record_update(db, commitment.id, raw_text=f"Sent back: {comment.strip()}", status_change="in_progress",
                           remaining=comment.strip(), source="coordinator", actor=actor)
        commitment = db.get(Commitment, commitment.id)
        commitment.marked_done_at = None
        db.add(commitment)
        db.commit()
        db.refresh(commitment)
        return commitment

    def create_manual(
        self, db: Session, *, description: str, assignee: Employee, assigned_by: str,
        assigned_by_user_id: Optional[UUID], due_date: Optional[datetime], department: str,
        notes: Optional[str] = None,
    ) -> Commitment:
        if not description.strip():
            raise CommitmentError("Describe the task")
        c = Commitment(
            assignee_employee_id=assignee.id, description=description.strip(), due_date=due_date,
            status="open", confidence=1.0, assigned_by=assigned_by, assigned_by_user_id=assigned_by_user_id,
            department=department,
        )
        db.add(c)
        db.commit()
        db.refresh(c)
        self.record_update(db, c.id, raw_text=(notes or "").strip() or "Task assigned",
                           source="coordinator", actor=assigned_by)
        db.refresh(c)
        return c

    # ── reading ─────────────────────────────────────────────────────────────
    def timeline(self, db: Session, commitment_id: UUID) -> list[CommitmentUpdate]:
        return list(db.exec(
            select(CommitmentUpdate).where(CommitmentUpdate.commitment_id == commitment_id)
            .order_by(CommitmentUpdate.created_at)
        ))

    def source_line(self, db: Session, commitment: Commitment) -> Optional[dict]:
        """The owner's utterance in the source meeting that best matches the task (word overlap).

        Extraction does not record the exact sentence, so the UI labels this "most likely".
        """
        if not commitment.source_meeting_id:
            return None
        from app.models.structured import Fragment

        frags = list(db.exec(select(Fragment).where(Fragment.meeting_id == commitment.source_meeting_id)))
        owner = db.get(Employee, commitment.assignee_employee_id) if commitment.assignee_employee_id else None
        if owner:
            frags = [f for f in frags if f.author_employee_id == owner.id] or frags
        words = set(re.findall(r"[a-z]{4,}", commitment.description.lower()))
        best, score = None, 0
        for f in frags:
            overlap = len(words & set(re.findall(r"[a-z]{4,}", f.content.lower())))
            if overlap > score:
                best, score = f, overlap
        if not best or score < 2:
            return None
        return {"text": best.content, "speaker": owner.display_name if owner else None}


def _aware(dt: Optional[datetime]) -> Optional[datetime]:
    return dt.replace(tzinfo=timezone.utc) if dt and dt.tzinfo is None else dt


def summarize(items: list[Commitment], now: Optional[datetime] = None) -> dict:
    """Counts for a set of tasks: open, overdue, due this week, blocked, awaiting confirmation, progress."""
    now = now or datetime.now(timezone.utc)
    active = [c for c in items if c.status in _OPEN_STATUSES]
    week = now + timedelta(days=7)
    return {
        "open": len(active),
        "overdue": sum(1 for c in active if c.due_date and _aware(c.due_date) < now),
        "due_this_week": sum(1 for c in active if c.due_date and now <= _aware(c.due_date) <= week),
        "blocked": sum(1 for c in active if c.status == "blocked"),
        "awaiting_confirmation": sum(1 for c in items if c.status == "review"),
        "completed": sum(1 for c in items if c.status == "done"),
        "average_progress": round(sum(c.progress for c in active) / len(active)) if active else None,
    }


commitment_service = CommitmentService()
