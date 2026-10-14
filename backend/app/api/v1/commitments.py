"""
Commitment (task) API.

Who may do what (enforced here):
  - the owner updates progress, what's left, blockers and notes, and marks the task done
    (→ ``review``, awaiting confirmation);
  - coordinators and administrators confirm or send back, create tasks, reassign and
    change due dates or any status;
  - everyone else on staff can read tasks within their department scope.
"""
from datetime import datetime
from typing import Optional
from uuid import UUID

import structlog
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlmodel import Session, select

from app.api.v1.auth import _ROLE_RANK, department_scope, parse_department, require_role, require_staff
from app.core.db import get_session
from app.models.structured import Commitment, Employee, Meeting, User
from app.services.audit_service import audit_service
from app.services.commitment_service import (
    OWNER_STATUSES, VALID_STATUSES, CommitmentError, commitment_service, summarize,
)
from app.services.employee_service import employee_service
from app.services.notice_service import notice_service

log = structlog.get_logger()
router = APIRouter()


class StatusUpdate(BaseModel):
    status: Optional[str] = None
    due_date: Optional[datetime] = None
    assignee_user_id: Optional[str] = None  # reassign (coordinator)


class ProgressUpdate(BaseModel):
    progress: Optional[int] = Field(default=None, ge=0, le=100)
    remaining: Optional[str] = Field(default=None, max_length=500)
    blocked_reason: Optional[str] = Field(default=None, max_length=500)
    note: Optional[str] = Field(default=None, max_length=2000)
    status: Optional[str] = None  # open / in_progress / blocked


class SendBack(BaseModel):
    comment: str = Field(min_length=1, max_length=1000)


class TaskCreate(BaseModel):
    description: str = Field(min_length=1, max_length=1000)
    assignee_user_id: str
    due_date: Optional[datetime] = None
    notes: Optional[str] = Field(default=None, max_length=2000)
    department: Optional[str] = None


def _is_coordinator(user: User) -> bool:
    return _ROLE_RANK.get(user.role, -1) >= _ROLE_RANK["manager"]


def _owner_user(db: Session, c: Commitment) -> Optional[User]:
    emp = db.get(Employee, c.assignee_employee_id) if c.assignee_employee_id else None
    return db.get(User, emp.user_id) if emp and emp.user_id else None


def _is_owner(db: Session, c: Commitment, user: User) -> bool:
    owner = _owner_user(db, c)
    return owner is not None and owner.id == user.id


def _serialize(db: Session, c: Commitment, *, viewer: Optional[User] = None) -> dict:
    emp = db.get(Employee, c.assignee_employee_id) if c.assignee_employee_id else None
    meeting = db.get(Meeting, c.source_meeting_id) if c.source_meeting_id else None
    out = {
        "id": str(c.id),
        "description": c.description,
        "assignee": emp.display_name if emp else None,
        "assignee_employee_id": str(c.assignee_employee_id) if c.assignee_employee_id else None,
        "status": c.status,
        "progress": c.progress,
        "remaining": c.remaining,
        "blocked_reason": c.blocked_reason,
        "due_date": c.due_date.isoformat() if c.due_date else None,
        "source_meeting_id": str(c.source_meeting_id) if c.source_meeting_id else None,
        "source_meeting": meeting.title if meeting else None,
        "assigned_by": c.assigned_by,
        "department": c.department,
        "confidence": c.confidence,
        "last_followup_at": c.last_followup_at.isoformat() if c.last_followup_at else None,
        "marked_done_at": c.marked_done_at.isoformat() if c.marked_done_at else None,
        "confirmed_at": c.confirmed_at.isoformat() if c.confirmed_at else None,
        "confirmed_by": c.confirmed_by,
        "created_at": c.created_at.isoformat(),
    }
    if viewer is not None:
        out["can_update"] = _is_owner(db, c, viewer)
        out["can_manage"] = _is_coordinator(viewer)
    return out


def _scoped(db: Session, user: User, stmt):
    scope = department_scope(user)
    return stmt.where(Commitment.department.in_(scope)) if scope is not None else stmt


def _get(db: Session, commitment_id: str, user: User) -> Commitment:
    try:
        c = db.get(Commitment, UUID(commitment_id))
    except ValueError:
        c = None
    scope = department_scope(user)
    # Owners always see their own task; others only within their department scope.
    if not c or (scope is not None and c.department not in scope and not _is_owner(db, c, user)):
        raise HTTPException(status_code=404, detail="Task not found")
    return c


def _notify_owner(db: Session, actor: User, c: Commitment, title: str, body: str) -> None:
    owner = _owner_user(db, c)
    if owner:
        notice_service.notify(db, actor, [owner], title, body)


def _notify_assigner(db: Session, actor: User, c: Commitment, title: str, body: str) -> None:
    recipients = []
    if c.assigned_by_user_id:
        recipients.append(db.get(User, c.assigned_by_user_id))
    if not recipients:  # meeting tasks with no recorded uploader: tell the coordinators in scope
        recipients = [u for u in db.exec(select(User).where(User.role == "manager", User.is_active == True))  # noqa: E712
                      if c.department == "all" or u.department in (None, c.department)]
    notice_service.notify(db, actor, [u for u in recipients if u], title, body)


# ── lists ───────────────────────────────────────────────────────────────────
@router.get("")
def list_commitments(
    status: Optional[str] = None,
    current_user: User = Depends(require_staff),
    db: Session = Depends(get_session),
):
    """All tasks in the caller's department scope."""
    if status and status not in VALID_STATUSES:
        raise HTTPException(status_code=400, detail=f"Invalid status filter '{status}'")
    stmt = _scoped(db, current_user, select(Commitment).order_by(Commitment.created_at.desc()))
    if status:
        stmt = stmt.where(Commitment.status == status)
    return [_serialize(db, c, viewer=current_user) for c in db.exec(stmt)]


@router.get("/mine")
def my_commitments(
    open_only: bool = False,
    current_user: User = Depends(require_staff),
    db: Session = Depends(get_session),
):
    employee = employee_service.get_or_create_for_user(db, current_user)
    commitments = commitment_service.for_employee(db, employee.id, open_only=open_only)
    return [_serialize(db, c, viewer=current_user) for c in commitments]


@router.get("/my-work")
def my_work(current_user: User = Depends(require_staff), db: Session = Depends(get_session)):
    """The caller's own tasks plus a summary (open, overdue, due this week, average progress)."""
    employee = employee_service.get_or_create_for_user(db, current_user)
    items = commitment_service.for_employee(db, employee.id)
    out = {"summary": summarize(items), "items": [_serialize(db, c, viewer=current_user) for c in items]}
    if _is_coordinator(current_user):
        waiting = db.exec(_scoped(db, current_user, select(Commitment).where(Commitment.status == "review")))
        out["awaiting_my_confirmation"] = [_serialize(db, c, viewer=current_user) for c in waiting]
    return out


@router.get("/team")
def team(current_user: User = Depends(require_role("manager")), db: Session = Depends(get_session)):
    """Everyone's tasks grouped by owner, for coordinators (scoped like everything else)."""
    groups: dict[str, dict] = {}
    for c in db.exec(_scoped(db, current_user, select(Commitment).order_by(Commitment.due_date))):
        emp = db.get(Employee, c.assignee_employee_id) if c.assignee_employee_id else None
        key = str(emp.id) if emp else "unassigned"
        g = groups.setdefault(key, {"owner": emp.display_name if emp else "Unassigned", "items": []})
        g["items"].append(c)
    return [
        {"owner": g["owner"], "summary": summarize(g["items"]),
         "items": [_serialize(db, c, viewer=current_user) for c in g["items"]]}
        for g in sorted(groups.values(), key=lambda g: -summarize(g["items"])["overdue"])
    ]


@router.get("/assignable")
def assignable(current_user: User = Depends(require_role("manager")), db: Session = Depends(get_session)):
    """Staff a coordinator can assign a task to."""
    users = db.exec(select(User).where(User.role != "student", User.is_active == True).order_by(User.full_name))  # noqa: E712
    return [{"user_id": str(u.id), "name": u.full_name or u.email, "department": u.department, "role": u.role}
            for u in users]


# ── one task ────────────────────────────────────────────────────────────────
@router.get("/{commitment_id}")
def task_detail(commitment_id: str, current_user: User = Depends(require_staff), db: Session = Depends(get_session)):
    c = _get(db, commitment_id, current_user)
    return {
        **_serialize(db, c, viewer=current_user),
        "source_line": commitment_service.source_line(db, c),
        "timeline": [
            {"at": u.created_at.isoformat(), "source": u.source, "actor": u.actor, "text": u.raw_text,
             "summary": u.structured_summary, "status": u.status_change, "progress": u.progress}
            for u in commitment_service.timeline(db, c.id)
        ],
    }


@router.post("/{commitment_id}/progress")
def update_progress(
    commitment_id: str, req: ProgressUpdate,
    current_user: User = Depends(require_staff), db: Session = Depends(get_session),
):
    """Owner: progress %, what's left, blocker, note, or a status among open / in_progress / blocked."""
    c = _get(db, commitment_id, current_user)
    if not _is_owner(db, c, current_user):
        raise HTTPException(status_code=403, detail="Only the task's owner can update its progress")
    if c.status in ("done", "dropped"):
        raise HTTPException(status_code=400, detail="This task is closed")
    if req.status and req.status not in ("open", "in_progress", "blocked"):
        raise HTTPException(status_code=400, detail="Use 'Mark done' to finish a task")
    if req.status == "blocked" and not (req.blocked_reason or "").strip():
        raise HTTPException(status_code=400, detail="Say what is blocking it")
    text = (req.note or "").strip() or "Progress updated"
    commitment_service.record_update(
        db, c.id, raw_text=text, status_change=req.status, progress=req.progress, remaining=req.remaining,
        blocked_reason=req.blocked_reason, source="owner", actor=current_user.full_name or current_user.email,
    )
    db.refresh(c)
    if c.status == "blocked" and req.blocked_reason:
        _notify_assigner(db, current_user, c, f"Task blocked: {c.description[:120]}",
                         f"{current_user.full_name or current_user.email} is blocked: {req.blocked_reason}")
    return _serialize(db, c, viewer=current_user)


@router.post("/{commitment_id}/done")
def mark_done(commitment_id: str, current_user: User = Depends(require_staff), db: Session = Depends(get_session)):
    """Owner: finished → awaiting a coordinator's confirmation."""
    c = _get(db, commitment_id, current_user)
    if not _is_owner(db, c, current_user):
        raise HTTPException(status_code=403, detail="Only the task's owner can mark it done")
    if c.status not in ("open", "in_progress", "blocked"):
        raise HTTPException(status_code=400, detail="This task is not open")
    commitment_service.record_update(db, c.id, raw_text="Marked done", status_change="review",
                                     source="owner", actor=current_user.full_name or current_user.email)
    db.refresh(c)
    _notify_assigner(db, current_user, c, f"Ready to confirm: {c.description[:120]}",
                     f"{current_user.full_name or current_user.email} marked this task done. Confirm it or send it back "
                     "on the My Work page.")
    return _serialize(db, c, viewer=current_user)


@router.post("/{commitment_id}/confirm")
def confirm(commitment_id: str, current_user: User = Depends(require_role("manager")), db: Session = Depends(get_session)):
    c = _get(db, commitment_id, current_user)
    try:
        c = commitment_service.confirm(db, c, current_user.full_name or current_user.email)
    except CommitmentError as e:
        raise HTTPException(status_code=400, detail=str(e))
    audit_service.record(db, actor=current_user.email, action="task_confirm", target_id=str(c.id))
    _notify_owner(db, current_user, c, f"Task completed: {c.description[:120]}",
                  f"{current_user.full_name or current_user.email} confirmed this task as completed.")
    return _serialize(db, c, viewer=current_user)


@router.post("/{commitment_id}/send-back")
def send_back(
    commitment_id: str, req: SendBack,
    current_user: User = Depends(require_role("manager")), db: Session = Depends(get_session),
):
    c = _get(db, commitment_id, current_user)
    try:
        c = commitment_service.send_back(db, c, current_user.full_name or current_user.email, req.comment)
    except CommitmentError as e:
        raise HTTPException(status_code=400, detail=str(e))
    audit_service.record(db, actor=current_user.email, action="task_send_back", target_id=str(c.id),
                         metadata={"comment": req.comment})
    _notify_owner(db, current_user, c, f"Task sent back: {c.description[:120]}",
                  f"{current_user.full_name or current_user.email}: {req.comment}")
    return _serialize(db, c, viewer=current_user)


@router.post("", status_code=201)
def create_task(req: TaskCreate, current_user: User = Depends(require_role("manager")), db: Session = Depends(get_session)):
    """Coordinator assigns a task directly (no meeting)."""
    try:
        owner = db.get(User, UUID(req.assignee_user_id))
    except ValueError:
        owner = None
    if not owner or owner.role == "student" or not owner.is_active:
        raise HTTPException(status_code=400, detail="Choose an active staff member")
    department = parse_department(req.department) if req.department else (owner.department or "all")
    emp = employee_service.get_or_create_for_user(db, owner)
    try:
        c = commitment_service.create_manual(
            db, description=req.description, assignee=emp, assigned_by=current_user.full_name or current_user.email,
            assigned_by_user_id=current_user.id, due_date=req.due_date, department=department, notes=req.notes,
        )
    except CommitmentError as e:
        raise HTTPException(status_code=400, detail=str(e))
    audit_service.record(db, actor=current_user.email, action="task_create", target_id=str(c.id),
                         metadata={"assignee": owner.email})
    _notify_owner(db, current_user, c, f"New task: {c.description[:120]}",
                  f"{current_user.full_name or current_user.email} assigned you a task"
                  + (f", due {req.due_date.date().isoformat()}" if req.due_date else "") + ". See My Work.")
    return _serialize(db, c, viewer=current_user)


@router.patch("/{commitment_id}")
def update_commitment(
    commitment_id: str, update: StatusUpdate,
    current_user: User = Depends(require_staff), db: Session = Depends(get_session),
):
    """Status change. Owners: open / in_progress / blocked / review. Coordinators: any status, due date, reassign."""
    if update.status is not None and update.status not in VALID_STATUSES:
        raise HTTPException(status_code=400, detail=f"Invalid status '{update.status}'. Allowed: {sorted(VALID_STATUSES)}")
    c = _get(db, commitment_id, current_user)
    coordinator = _is_coordinator(current_user)
    if not coordinator and not _is_owner(db, c, current_user):
        raise HTTPException(status_code=403, detail="Only the task's owner or a coordinator can change it")
    if update.status is not None:
        if not coordinator and update.status not in OWNER_STATUSES:
            raise HTTPException(status_code=403, detail="A coordinator confirms completion")
    if (update.due_date is not None or update.assignee_user_id) and not coordinator:
        raise HTTPException(status_code=403, detail="Only a coordinator can change the due date or owner")
    actor = current_user.full_name or current_user.email
    if update.status is not None:
        commitment_service.record_update(db, c.id, raw_text=f"Status set to {update.status.replace('_', ' ')}",
                                         status_change=update.status, actor=actor,
                                         source="coordinator" if coordinator and not _is_owner(db, c, current_user) else "owner")
    if update.due_date is not None:
        c = db.get(Commitment, c.id)
        c.due_date = update.due_date
        db.add(c)
        db.commit()
        commitment_service.record_update(db, c.id, raw_text=f"Due date set to {update.due_date.date().isoformat()}",
                                         source="coordinator", actor=actor)
    if update.assignee_user_id:
        try:
            new_owner = db.get(User, UUID(update.assignee_user_id))
        except ValueError:
            new_owner = None
        if not new_owner or new_owner.role == "student":
            raise HTTPException(status_code=400, detail="Choose a staff member")
        c = db.get(Commitment, c.id)
        c.assignee_employee_id = employee_service.get_or_create_for_user(db, new_owner).id
        db.add(c)
        db.commit()
        commitment_service.record_update(db, c.id, raw_text=f"Reassigned to {new_owner.full_name or new_owner.email}",
                                         source="coordinator", actor=actor)
        notice_service.notify(db, current_user, [new_owner], f"Task reassigned to you: {c.description[:120]}",
                              f"{actor} reassigned this task to you. See My Work.")
    c = db.get(Commitment, c.id)
    return _serialize(db, c, viewer=current_user)
