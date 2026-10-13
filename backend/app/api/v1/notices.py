"""Notices: staff send to filtered audiences; everyone reads their own inbox."""
from datetime import datetime
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlmodel import Session

from app.api.v1.auth import get_current_user, require_staff
from app.core.db import get_session
from app.models.structured import User
from app.services.notice_service import NoticeError, notice_service

router = APIRouter()


class Audience(BaseModel):
    roles: list[str] = Field(default_factory=lambda: ["student"])
    departments: list[str] = Field(default_factory=list)
    years: list[int] = Field(default_factory=list)
    semesters: list[int] = Field(default_factory=list)
    divisions: list[str] = Field(default_factory=list)


class NoticeCreate(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    body: str = Field(min_length=1, max_length=10_000)
    priority: str = "normal"
    expires_at: Optional[datetime] = None
    audience: Audience = Field(default_factory=Audience)


@router.post("/preview")
def preview(req: Audience, current_user: User = Depends(require_staff), db: Session = Depends(get_session)):
    """How many people an audience reaches (and the audience after sender rules are applied)."""
    try:
        return notice_service.preview(db, current_user, req.model_dump())
    except NoticeError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("", status_code=201)
def send(req: NoticeCreate, current_user: User = Depends(require_staff), db: Session = Depends(get_session)):
    try:
        notice, count = notice_service.send(
            db, current_user, title=req.title, body=req.body, audience=req.audience.model_dump(),
            priority=req.priority, expires_at=req.expires_at,
        )
    except NoticeError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return {"id": str(notice.id), "recipients": count}


@router.get("/mine")
def inbox(current_user: User = Depends(get_current_user), db: Session = Depends(get_session)):
    return notice_service.inbox(db, current_user)


@router.get("/unread-count")
def unread_count(current_user: User = Depends(get_current_user), db: Session = Depends(get_session)):
    return {"unread": notice_service.unread_count(db, current_user)}


@router.post("/{notice_id}/read")
def mark_read(notice_id: str, current_user: User = Depends(get_current_user), db: Session = Depends(get_session)):
    try:
        nid = UUID(notice_id)
    except ValueError:
        raise HTTPException(status_code=404, detail="Notice not found")
    if not notice_service.mark_read(db, current_user, nid):
        raise HTTPException(status_code=404, detail="Notice not found")  # not addressed to this user
    return {"ok": True}


@router.get("/sent")
def sent(current_user: User = Depends(require_staff), db: Session = Depends(get_session)):
    return notice_service.sent(db, current_user)
