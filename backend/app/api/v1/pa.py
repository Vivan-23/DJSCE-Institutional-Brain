"""Company PA API — proactive follow-ups and the end-of-day check-in (FR1c)."""
import json
from uuid import UUID

import structlog
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlmodel import Session

from app.api.v1.auth import require_staff
from app.core.db import get_session
from app.models.structured import CheckIn, User
from app.services.employee_service import employee_service
from app.services.pa_service import pa_service

log = structlog.get_logger()
router = APIRouter()


class ReplyRequest(BaseModel):
    text: str


class MessageRequest(BaseModel):
    text: str


def _serialize_checkin(ci: CheckIn) -> dict:
    def _load(raw):
        try:
            return json.loads(raw) if raw else []
        except (json.JSONDecodeError, TypeError):
            return []

    return {
        "id": str(ci.id),
        "date": ci.date.isoformat(),
        "completed": ci.completed,
        "conversation": _load(ci.conversation),
        "extracted_updates": _load(ci.extracted_updates),
    }


@router.get("/followups")
def list_followups(
    current_user: User = Depends(require_staff),
    db: Session = Depends(get_session),
):
    employee = employee_service.get_or_create_for_user(db, current_user)
    return pa_service.pending_followups(db, employee)


@router.post("/followups/{commitment_id}/reply")
def reply_to_followup(
    commitment_id: str,
    req: ReplyRequest,
    current_user: User = Depends(require_staff),
    db: Session = Depends(get_session),
):
    if not req.text.strip():
        raise HTTPException(status_code=400, detail="Reply text is required")
    try:
        cid = UUID(commitment_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid commitment id")
    employee = employee_service.get_or_create_for_user(db, current_user)
    result = pa_service.record_followup_reply(db, employee, cid, req.text.strip())
    if result is None:
        raise HTTPException(status_code=404, detail="Commitment not found or not assigned to you")
    return result


@router.get("/checkin")
def get_checkin(
    current_user: User = Depends(require_staff),
    db: Session = Depends(get_session),
):
    employee = employee_service.get_or_create_for_user(db, current_user)
    checkin = pa_service.get_today_checkin(db, employee)
    return _serialize_checkin(checkin)


@router.post("/checkin/message")
def post_checkin_message(
    req: MessageRequest,
    current_user: User = Depends(require_staff),
    db: Session = Depends(get_session),
):
    if not req.text.strip():
        raise HTTPException(status_code=400, detail="Message text is required")
    employee = employee_service.get_or_create_for_user(db, current_user)
    checkin = pa_service.get_today_checkin(db, employee)
    if checkin.completed:
        raise HTTPException(status_code=409, detail="Today's check-in is already complete")
    return pa_service.checkin_message(db, employee, checkin, req.text.strip())


@router.post("/checkin/complete")
def complete_checkin(
    current_user: User = Depends(require_staff),
    db: Session = Depends(get_session),
):
    employee = employee_service.get_or_create_for_user(db, current_user)
    checkin = pa_service.get_today_checkin(db, employee)
    pa_service.complete_checkin(db, checkin)
    return _serialize_checkin(checkin)
