"""Meeting transcript ingestion — the Phase-1 capture entry point."""
import json
from datetime import datetime
from typing import Optional
from uuid import UUID

import structlog
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import Response
from pydantic import BaseModel
from sqlmodel import Session, select

from app.api.v1.auth import department_scope, parse_department, require_role, require_staff
from app.core.db import get_session
from app.models.structured import Meeting, User

log = structlog.get_logger()
router = APIRouter()

MAX_TRANSCRIPT_CHARS = 200_000


class TranscriptRequest(BaseModel):
    title: str
    transcript: str
    source: str = "upload"
    occurred_at: Optional[datetime] = None
    department: Optional[str] = None  # owning department code; omitted = institution-wide


@router.post("", status_code=202)
def ingest_transcript(
    req: TranscriptRequest,
    current_user: User = Depends(require_staff),
):
    text = req.transcript.strip()
    if not text:
        raise HTTPException(status_code=400, detail="Transcript is empty")
    if len(text) > MAX_TRANSCRIPT_CHARS:
        raise HTTPException(
            status_code=413,
            detail=f"Transcript exceeds {MAX_TRANSCRIPT_CHARS} character limit",
        )
    if not req.title.strip():
        raise HTTPException(status_code=400, detail="Title is required")

    department = parse_department(req.department)
    from app.core.celery import process_transcript_task
    occurred = req.occurred_at.isoformat() if req.occurred_at else None
    task = process_transcript_task.delay(text, req.title.strip(), req.source, department, occurred)

    log.info("Transcript queued", title=req.title, user=current_user.email, task_id=task.id)
    return {
        "title": req.title,
        "status": "queued",
        "task_id": task.id,
        "message": "Transcript is being processed. Meeting, decisions, and commitments will appear shortly.",
    }


@router.get("")
def list_meetings(
    current_user: User = Depends(require_staff),
    db: Session = Depends(get_session),
):
    stmt = select(Meeting).order_by(Meeting.occurred_at.desc())
    scope = department_scope(current_user)
    if scope is not None:  # faculty: their department's meetings + institution-wide ones
        stmt = stmt.where(Meeting.department.in_(scope))
    meetings = db.exec(stmt).all()
    return [
        {
            "id": str(m.id),
            "title": m.title,
            "occurred_at": m.occurred_at.isoformat(),
            "summary": m.summary,
            "source": m.source,
            "department": m.department,
        }
        for m in meetings
    ]


def _get_scoped(db: Session, meeting_id: str, user: User) -> Meeting:
    """The meeting, or 404 if missing or outside the user's department scope."""
    try:
        mid = UUID(meeting_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid meeting id")
    meeting = db.get(Meeting, mid)
    scope = department_scope(user)
    if not meeting or (scope is not None and meeting.department not in scope):
        raise HTTPException(status_code=404, detail="Meeting not found")
    return meeting


@router.get("/{meeting_id}")
def get_meeting(
    meeting_id: str,
    current_user: User = Depends(require_staff),
    db: Session = Depends(get_session),
):
    meeting = _get_scoped(db, meeting_id, current_user)
    return {
        "id": str(meeting.id),
        "title": meeting.title,
        "occurred_at": meeting.occurred_at.isoformat(),
        "summary": meeting.summary,
        "source": meeting.source,
        "department": meeting.department,
        "participants": json.loads(meeting.participants or "[]"),
        "decisions": json.loads(meeting.decisions or "[]"),
        "raw_transcript": meeting.raw_transcript,
    }


_MINUTES_TYPES = {
    "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "pdf": "application/pdf",
}


@router.get("/{meeting_id}/minutes")
def export_minutes(
    meeting_id: str,
    format: str = Query("docx", pattern="^(docx|pdf)$"),
    current_user: User = Depends(require_role("manager")),
    db: Session = Depends(get_session),
):
    """Formal draft minutes (DOCX or PDF) built from the stored extraction. Coordinator+; audited."""
    from app.services.audit_service import audit_service
    from app.services.minutes_service import minutes_service

    meeting = _get_scoped(db, meeting_id, current_user)
    minutes = minutes_service.build(db, meeting)
    body = minutes_service.to_pdf(minutes) if format == "pdf" else minutes_service.to_docx(minutes)
    audit_service.record(db, actor=current_user.email, action="minutes_export", target_id=str(meeting.id),
                         metadata={"format": format})
    return Response(
        content=body,
        media_type=_MINUTES_TYPES[format],
        headers={"Content-Disposition": f'attachment; filename="{minutes_service.filename(minutes, format)}"'},
    )
