"""Teaching schedule API: a faculty member's dated lectures and date-specific changes.

Reads come from published timetables only (schedule_service); timetable upload and review
live in ``timetables.py``. Changes to single dates (cancel, reschedule, holiday, extra
lecture) are coordinator actions, audited, and announced to the affected faculty.
"""
from datetime import date, timedelta
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlmodel import Session, select

from app.api.v1.auth import require_role, require_staff
from app.core.db import get_session
from app.models.structured import ScheduleException, TimetableEntry, TimetableImport, User
from app.services.audit_service import audit_service
from app.services.notice_service import notice_service
from app.services.schedule_service import (
    MAX_RANGE_DAYS, ScheduleError, as_day, class_label, local_today, schedule_service,
)

router = APIRouter()


class ExceptionCreate(BaseModel):
    on_date: date
    kind: str
    entry_id: Optional[UUID] = None
    faculty_user_id: Optional[UUID] = None
    department: str = "all"
    start_time: Optional[str] = None
    end_time: Optional[str] = None
    room: Optional[str] = Field(default=None, max_length=60)
    subject: Optional[str] = Field(default=None, max_length=120)
    class_label: Optional[str] = Field(default=None, max_length=60)
    reason: Optional[str] = Field(default=None, max_length=300)


def _serialize_exception(db: Session, ex: ScheduleException) -> dict:
    entry = db.get(TimetableEntry, ex.entry_id) if ex.entry_id else None
    imp = db.get(TimetableImport, entry.import_id) if entry else None
    return {
        "id": str(ex.id), "date": ex.on_date.isoformat(), "kind": ex.kind,
        "entry_id": str(ex.entry_id) if ex.entry_id else None,
        "subject": ex.subject or (entry.subject if entry else None),
        "class_label": ex.class_label or (class_label(imp) if imp else None),
        "start_time": ex.start_time, "end_time": ex.end_time, "room": ex.room,
        "department": ex.department, "reason": ex.reason,
    }


@router.get("/mine")
def my_schedule(
    start: Optional[date] = None,
    days: int = 7,
    current_user: User = Depends(require_staff),
    db: Session = Depends(get_session),
):
    """The caller's lectures from start (default: today, institution timezone) for ``days`` days."""
    start = start or local_today()
    try:
        items = schedule_service.occurrences(db, current_user, start, days)
    except ScheduleError as e:
        raise HTTPException(status_code=400, detail=str(e))
    has_timetable = bool(schedule_service.published_entries(db, current_user.id))
    return {"start": start.isoformat(), "days": days, "today": local_today().isoformat(),
            "has_timetable": has_timetable, "items": items}


@router.get("/load")
def my_load(current_user: User = Depends(require_staff), db: Session = Depends(get_session)):
    return schedule_service.weekly_load(db, current_user.id)


@router.get("/exceptions")
def list_exceptions(
    start: Optional[date] = None,
    days: int = 31,
    current_user: User = Depends(require_staff),
    db: Session = Depends(get_session),
):
    if days < 1 or days > MAX_RANGE_DAYS * 3:
        raise HTTPException(status_code=400, detail="days out of range")
    start = start or local_today()
    rows = db.exec(select(ScheduleException)
                   .where(ScheduleException.on_date >= as_day(start))
                   .where(ScheduleException.on_date < as_day(start + timedelta(days=days)))
                   .order_by(ScheduleException.on_date))
    return [_serialize_exception(db, ex) for ex in rows]


def _affected(db: Session, ex: ScheduleException) -> list[User]:
    if ex.kind == "extra" and ex.faculty_user_id:
        return [db.get(User, ex.faculty_user_id)]
    if ex.entry_id:
        entry = db.get(TimetableEntry, ex.entry_id)
        return [db.get(User, entry.faculty_user_id)] if entry and entry.faculty_user_id else []
    # holiday: every faculty member who teaches from a published timetable
    ids = {e.faculty_user_id for e, imp in db.exec(
        select(TimetableEntry, TimetableImport).where(TimetableEntry.import_id == TimetableImport.id)
        .where(TimetableImport.status == "published")) if e.faculty_user_id}
    return [u for u in (db.get(User, i) for i in ids) if u and ex.department in ("all", u.department)]


_KIND_TITLE = {"cancelled": "Lecture cancelled", "modified": "Lecture rescheduled",
               "holiday": "No teaching (holiday)", "extra": "Extra lecture scheduled"}


@router.post("/exceptions", status_code=201)
def create_exception(
    req: ExceptionCreate,
    current_user: User = Depends(require_role("manager")),
    db: Session = Depends(get_session),
):
    try:
        ex = schedule_service.add_exception(
            db, current_user, on_date=req.on_date, kind=req.kind, entry_id=req.entry_id,
            faculty_user_id=req.faculty_user_id, department=req.department, start_time=req.start_time,
            end_time=req.end_time, room=req.room, subject=req.subject, class_label_text=req.class_label,
            reason=req.reason,
        )
    except ScheduleError as e:
        raise HTTPException(status_code=400, detail=str(e))
    out = _serialize_exception(db, ex)
    audit_service.record(db, actor=current_user.email, action="schedule_exception_created",
                         target_id=str(ex.id), metadata=out)
    what = " · ".join(p for p in (out["subject"], out["class_label"]) if p)
    body = f"{out['date']}{' — ' + what if what else ''}."
    if ex.kind == "modified":
        body += f" New slot: {ex.start_time or ''}{'-' + ex.end_time if ex.end_time else ''} {ex.room or ''}".rstrip() + "."
    if ex.reason:
        body += f" Reason: {ex.reason}"
    notice_service.notify(db, current_user, _affected(db, ex), _KIND_TITLE[ex.kind], body)
    return out


@router.delete("/exceptions/{exception_id}", status_code=204)
def delete_exception(
    exception_id: UUID,
    current_user: User = Depends(require_role("manager")),
    db: Session = Depends(get_session),
):
    ex = db.get(ScheduleException, exception_id)
    if not ex:
        raise HTTPException(status_code=404, detail="Change not found")
    snapshot = _serialize_exception(db, ex)
    affected = _affected(db, ex)
    db.delete(ex)
    db.commit()
    audit_service.record(db, actor=current_user.email, action="schedule_exception_removed",
                         target_id=str(exception_id), metadata=snapshot)
    notice_service.notify(db, current_user, affected, "Timetable change withdrawn",
                          f"The {snapshot['kind']} change on {snapshot['date']} was withdrawn; the regular timetable applies.")
