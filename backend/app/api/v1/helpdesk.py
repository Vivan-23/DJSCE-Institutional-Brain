"""Help Desk API — students raise tickets; faculty triage and send human-approved replies.

Access is by responsibility, not rank: students and faculty use the Help Desk, faculty
handle the queue, administrators may read it. Coordinators get 403 (V2 product rule)."""
import json
from typing import Any, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlmodel import Session

from app.api.v1.auth import (
    is_staff, require_exact_roles, require_helpdesk_user, require_ticket_handler, require_ticket_reader,
)
from app.core.db import get_session
from app.core.institution_config import get_institution_config
from app.models.structured import Ticket, User
from app.services.ticket_service import TICKET_STATUSES, ticket_service

router = APIRouter()

# Reading one ticket: its requester (student/faculty), faculty handlers, or an admin.
require_ticket_viewer = require_exact_roles("student", "employee", "admin")


class TicketCreate(BaseModel):
    subject: str = Field(min_length=3, max_length=200)
    description: str = Field(min_length=5, max_length=5000)


class TicketReply(BaseModel):
    reply: str = Field(min_length=1, max_length=8000)
    close: bool = False


class TicketStatus(BaseModel):
    status: str


def _serialize(db: Session, t: Ticket, *, staff_view: bool) -> dict[str, Any]:
    out: dict[str, Any] = {
        "id": str(t.id),
        "subject": t.subject,
        "description": t.description,
        "status": t.status,
        "category": t.category,
        "priority": t.priority,
        "routed_to": t.routed_to,
        "reply": t.reply,
        "replied_at": t.replied_at.isoformat() if t.replied_at else None,
        "created_at": t.created_at.isoformat(),
        "updated_at": t.updated_at.isoformat(),
    }
    if staff_view:
        raiser = db.get(User, t.raised_by_user_id)
        try:
            sources = json.loads(t.ai_sources or "[]")
        except json.JSONDecodeError:
            sources = []
        out.update(
            raised_by=raiser.full_name or raiser.email if raiser else None,
            raised_by_role=raiser.role if raiser else None,
            triage_method=t.triage_method,
            triage_rationale=t.triage_rationale,
            ai_draft_reply=t.ai_draft_reply,
            ai_sources=sources,
        )
    return out


def _get_visible(db: Session, ticket_id: str, user: User) -> Ticket:
    try:
        tid = UUID(ticket_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid ticket id")
    ticket = ticket_service.get(db, tid)
    # Non-staff can only see their own tickets; 404 (not 403) so ids can't be probed.
    if not ticket or (not is_staff(user) and ticket.raised_by_user_id != user.id):
        raise HTTPException(status_code=404, detail="Ticket not found")
    return ticket


@router.get("/categories")
def list_categories(current_user: User = Depends(require_helpdesk_user)):
    return [
        {"key": c.key, "label": c.label, "routed_to": c.routed_to, "quick_questions": c.quick_questions}
        for c in get_institution_config().helpdesk_categories
    ]


@router.post("/tickets", status_code=201)
def create_ticket(
    req: TicketCreate,
    current_user: User = Depends(require_helpdesk_user),
    db: Session = Depends(get_session),
):
    ticket = ticket_service.create(db, current_user, req.subject.strip(), req.description.strip())
    return _serialize(db, ticket, staff_view=False)


@router.get("/tickets/mine")
def my_tickets(current_user: User = Depends(require_helpdesk_user), db: Session = Depends(get_session)):
    return [_serialize(db, t, staff_view=False) for t in ticket_service.for_user(db, current_user.id)]


@router.get("/tickets")
def ticket_queue(
    status: Optional[str] = None,
    category: Optional[str] = None,
    current_user: User = Depends(require_ticket_reader),
    db: Session = Depends(get_session),
):
    if status and status not in TICKET_STATUSES:
        raise HTTPException(status_code=400, detail=f"Invalid status filter '{status}'")
    return [_serialize(db, t, staff_view=True) for t in ticket_service.queue(db, status=status, category=category)]


@router.get("/tickets/{ticket_id}")
def get_ticket(ticket_id: str, current_user: User = Depends(require_ticket_viewer), db: Session = Depends(get_session)):
    ticket = _get_visible(db, ticket_id, current_user)
    return _serialize(db, ticket, staff_view=is_staff(current_user))


@router.post("/tickets/{ticket_id}/reply")
def reply_ticket(
    ticket_id: str,
    req: TicketReply,
    current_user: User = Depends(require_ticket_handler),
    db: Session = Depends(get_session),
):
    ticket = _get_visible(db, ticket_id, current_user)
    updated = ticket_service.reply(db, ticket, current_user, req.reply.strip(), close=req.close)
    return _serialize(db, updated, staff_view=True)


@router.post("/tickets/{ticket_id}/retriage")
def retriage_ticket(ticket_id: str, current_user: User = Depends(require_ticket_handler), db: Session = Depends(get_session)):
    ticket = _get_visible(db, ticket_id, current_user)
    return _serialize(db, ticket_service.retriage(db, ticket, current_user.email), staff_view=True)


@router.patch("/tickets/{ticket_id}")
def update_ticket_status(
    ticket_id: str,
    req: TicketStatus,
    current_user: User = Depends(require_helpdesk_user),
    db: Session = Depends(get_session),
):
    ticket = _get_visible(db, ticket_id, current_user)
    if req.status not in TICKET_STATUSES:
        raise HTTPException(status_code=400, detail=f"Invalid status. Allowed: {sorted(TICKET_STATUSES)}")
    # Requesters may only close their own ticket; staff may set any status.
    if not is_staff(current_user) and req.status != "closed":
        raise HTTPException(status_code=403, detail="You can only close your own ticket")
    updated = ticket_service.set_status(db, ticket, req.status, current_user.email)
    return _serialize(db, updated, staff_view=is_staff(current_user))
