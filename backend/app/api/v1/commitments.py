"""Commitment (action item) API."""
from typing import Optional
from uuid import UUID

import structlog
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlmodel import Session

from app.api.v1.auth import require_staff
from app.core.db import get_session
from app.models.structured import Commitment, Employee, User
from app.services.commitment_service import commitment_service, VALID_STATUSES
from app.services.employee_service import employee_service

log = structlog.get_logger()
router = APIRouter()


class StatusUpdate(BaseModel):
    status: str


def _serialize(db: Session, c: Commitment) -> dict:
    assignee = None
    if c.assignee_employee_id:
        emp = db.get(Employee, c.assignee_employee_id)
        assignee = emp.display_name if emp else None
    return {
        "id": str(c.id),
        "description": c.description,
        "assignee": assignee,
        "assignee_employee_id": str(c.assignee_employee_id) if c.assignee_employee_id else None,
        "status": c.status,
        "due_date": c.due_date.isoformat() if c.due_date else None,
        "source_meeting_id": str(c.source_meeting_id) if c.source_meeting_id else None,
        "confidence": c.confidence,
        "last_followup_at": c.last_followup_at.isoformat() if c.last_followup_at else None,
        "created_at": c.created_at.isoformat(),
    }


@router.get("")
def list_commitments(
    status: Optional[str] = None,
    current_user: User = Depends(require_staff),
    db: Session = Depends(get_session),
):
    if status and status not in VALID_STATUSES:
        raise HTTPException(status_code=400, detail=f"Invalid status filter '{status}'")
    commitments = commitment_service.list_all(db, status=status)
    return [_serialize(db, c) for c in commitments]


@router.get("/mine")
def my_commitments(
    open_only: bool = False,
    current_user: User = Depends(require_staff),
    db: Session = Depends(get_session),
):
    employee = employee_service.get_or_create_for_user(db, current_user)
    commitments = commitment_service.for_employee(db, employee.id, open_only=open_only)
    return [_serialize(db, c) for c in commitments]


@router.patch("/{commitment_id}")
def update_commitment(
    commitment_id: str,
    update: StatusUpdate,
    current_user: User = Depends(require_staff),
    db: Session = Depends(get_session),
):
    try:
        cid = UUID(commitment_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid commitment id")
    if update.status not in VALID_STATUSES:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid status '{update.status}'. Allowed: {sorted(VALID_STATUSES)}",
        )
    commitment = commitment_service.update_status(db, cid, update.status)
    if not commitment:
        raise HTTPException(status_code=404, detail="Commitment not found")
    return _serialize(db, commitment)
