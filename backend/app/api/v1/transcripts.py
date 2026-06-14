"""Meeting transcript ingestion — the Phase-1 capture entry point."""
from datetime import datetime
from typing import Optional

import structlog
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlmodel import Session, select

from app.api.v1.auth import get_current_user
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


@router.post("", status_code=202)
def ingest_transcript(
    req: TranscriptRequest,
    current_user: User = Depends(get_current_user),
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

    from app.core.celery import process_transcript_task
    task = process_transcript_task.delay(text, req.title.strip(), req.source)

    log.info("Transcript queued", title=req.title, user=current_user.email, task_id=task.id)
    return {
        "title": req.title,
        "status": "queued",
        "task_id": task.id,
        "message": "Transcript is being processed. Meeting, decisions, and commitments will appear shortly.",
    }


@router.get("")
def list_meetings(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_session),
):
    meetings = db.exec(select(Meeting).order_by(Meeting.occurred_at.desc())).all()
    return [
        {
            "id": str(m.id),
            "title": m.title,
            "occurred_at": m.occurred_at.isoformat(),
            "summary": m.summary,
            "source": m.source,
        }
        for m in meetings
    ]


@router.get("/{meeting_id}")
def get_meeting(
    meeting_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_session),
):
    from uuid import UUID
    try:
        mid = UUID(meeting_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid meeting id")
    meeting = db.get(Meeting, mid)
    if not meeting:
        raise HTTPException(status_code=404, detail="Meeting not found")
    import json
    return {
        "id": str(meeting.id),
        "title": meeting.title,
        "occurred_at": meeting.occurred_at.isoformat(),
        "summary": meeting.summary,
        "source": meeting.source,
        "participants": json.loads(meeting.participants or "[]"),
        "raw_transcript": meeting.raw_transcript,
    }
