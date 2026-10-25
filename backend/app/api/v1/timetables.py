"""Timetable upload, review and publication (Committee Coordinators and administrators).

Upload returns 202 and extracts in the background into a *draft*; nothing reaches anyone's schedule until a
coordinator reviews the entries, maps every faculty abbreviation to a verified account, and publishes.
"""
import json
from datetime import date
from typing import Any, Optional
from uuid import UUID

import structlog
from fastapi import APIRouter, Depends, File, Form, HTTPException, Response, UploadFile
from pydantic import BaseModel, Field
from sqlmodel import Session, select

from app.api.v1.auth import parse_department, require_role
from app.core.db import get_session
from app.models.structured import FacultyAlias, TimetableEntry, TimetableImport, TimetableSource, User
from app.services.timetable_extract import MAX_UPLOAD_BYTES, kind_of
from app.services.timetable_service import BLOCKING, ISSUE_TEXT, TimetableError, timetable_service

log = structlog.get_logger()
router = APIRouter()
require_coordinator = require_role("manager")
DAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]


class HeaderUpdate(BaseModel):
    year_label: Optional[str] = Field(default=None, max_length=10)
    division: Optional[str] = Field(default=None, max_length=10)
    semester: Optional[str] = Field(default=None, max_length=10)
    academic_term: Optional[str] = Field(default=None, max_length=60)
    effective_from: Optional[date] = None


class EntryFields(BaseModel):
    weekday: Optional[int] = Field(default=None, ge=0, le=6)
    start_time: Optional[str] = None
    end_time: Optional[str] = None
    subject: Optional[str] = Field(default=None, max_length=60)
    room: Optional[str] = Field(default=None, max_length=60)
    faculty_abbrev: Optional[str] = Field(default=None, max_length=4)
    kind: Optional[str] = None
    batch: Optional[str] = Field(default=None, max_length=10)


class PublishRequest(BaseModel):
    acknowledge_warnings: bool = False


class AliasCreate(BaseModel):
    abbrev: str = Field(min_length=1, max_length=4)
    user_id: UUID


def _user_name(db: Session, uid: Optional[UUID]) -> Optional[str]:
    u = db.get(User, uid) if uid else None
    return (u.full_name or u.email) if u else None


def _entry(db: Session, e: TimetableEntry) -> dict[str, Any]:
    issues = json.loads(e.issues or "[]")
    valid_day = e.weekday is not None and 0 <= e.weekday <= 6
    return {
        "id": str(e.id), "weekday": e.weekday if valid_day else None, "day": DAYS[e.weekday] if valid_day else None,
        "start_time": e.start_time or None, "end_time": e.end_time or None, "subject": e.subject, "room": e.room,
        "faculty_abbrev": e.faculty_abbrev, "faculty_user_id": str(e.faculty_user_id) if e.faculty_user_id else None,
        "faculty_name": _user_name(db, e.faculty_user_id), "kind": e.kind, "batch": e.batch,
        "source_cell": e.source_cell, "edited": e.edited,
        "issues": [{"code": i, "text": ISSUE_TEXT.get(i, i), "blocking": i in BLOCKING} for i in issues],
    }


def _summary(db: Session, imp: TimetableImport) -> dict[str, Any]:
    entries = timetable_service.entries(db, imp)
    return {
        "id": str(imp.id), "class_key": imp.class_key or None,
        "class_label": " ".join(p for p in (imp.year_label, imp.division) if p) or None,
        "year_label": imp.year_label, "division": imp.division, "semester": imp.semester,
        "academic_term": imp.academic_term,
        "effective_from": imp.effective_from.isoformat() if imp.effective_from else None,
        "department": imp.department, "source_filename": imp.source_filename, "version": imp.version,
        "status": imp.status, "extraction_method": imp.extraction_method, "extraction_error": imp.extraction_error,
        "uploaded_by": _user_name(db, imp.uploaded_by_user_id), "created_at": imp.created_at.isoformat(),
        "published_at": imp.published_at.isoformat() if imp.published_at else None,
        "published_by": _user_name(db, imp.published_by_user_id),
        "counts": timetable_service.counts(entries),
    }


def _get(db: Session, import_id: UUID) -> TimetableImport:
    imp = db.get(TimetableImport, import_id)
    if not imp:
        raise HTTPException(status_code=404, detail="Timetable not found")
    return imp


def _get_entry(db: Session, imp: TimetableImport, entry_id: UUID) -> TimetableEntry:
    e = db.get(TimetableEntry, entry_id)
    if not e or e.import_id != imp.id:
        raise HTTPException(status_code=404, detail="Entry not found")
    return e


def _fail(e: TimetableError):
    raise HTTPException(status_code=400, detail=str(e))


# ── imports ─────────────────────────────────────────────────────────────────
@router.post("", status_code=202)
async def upload_timetable(
    response: Response,
    file: UploadFile = File(...),
    department: Optional[str] = Form(None),
    current_user: User = Depends(require_coordinator),
    db: Session = Depends(get_session),
):
    data = await file.read()
    if not data:
        raise HTTPException(status_code=400, detail="The file is empty")
    if len(data) > MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=413, detail="File exceeds 15 MB")
    if kind_of(file.filename or "", file.content_type or "") is None:
        raise HTTPException(status_code=400, detail="Upload a photo (PNG/JPG), PDF, Word (.docx), Excel (.xlsx) or CSV")
    imp, created = timetable_service.upload(db, current_user, file.filename or "timetable", file.content_type or "",
                                            data, parse_department(department))
    if not created:
        response.status_code = 200
        return {**_summary(db, imp), "duplicate": True,
                "message": "This exact file was already uploaded; opening the existing timetable."}
    from app.core.celery import process_timetable_task
    process_timetable_task.delay(str(imp.id))
    return {**_summary(db, imp), "duplicate": False}


@router.get("")
def list_timetables(current_user: User = Depends(require_coordinator), db: Session = Depends(get_session)):
    rows = db.exec(select(TimetableImport).where(TimetableImport.status != "discarded")
                   .order_by(TimetableImport.created_at.desc()))
    return [_summary(db, i) for i in rows]


@router.get("/aliases")
def list_aliases(current_user: User = Depends(require_coordinator), db: Session = Depends(get_session)):
    return [{"id": str(a.id), "abbrev": a.abbrev, "user_id": str(a.user_id), "name": _user_name(db, a.user_id),
             "verified_by": _user_name(db, a.verified_by_user_id), "created_at": a.created_at.isoformat()}
            for a in db.exec(select(FacultyAlias).order_by(FacultyAlias.abbrev))]


@router.post("/aliases", status_code=201)
def create_alias(req: AliasCreate, current_user: User = Depends(require_coordinator), db: Session = Depends(get_session)):
    try:
        a = timetable_service.add_alias(db, current_user, req.abbrev, req.user_id)
    except TimetableError as e:
        _fail(e)
    return {"id": str(a.id), "abbrev": a.abbrev, "user_id": str(a.user_id), "name": _user_name(db, a.user_id)}


@router.delete("/aliases/{alias_id}", status_code=204)
def delete_alias(alias_id: UUID, current_user: User = Depends(require_coordinator), db: Session = Depends(get_session)):
    a = db.get(FacultyAlias, alias_id)
    if not a:
        raise HTTPException(status_code=404, detail="Mapping not found")
    timetable_service.remove_alias(db, current_user, a)


@router.get("/staff")
def mappable_staff(current_user: User = Depends(require_coordinator), db: Session = Depends(get_session)):
    """Accounts initials may be mapped to (active staff)."""
    users = db.exec(select(User).where(User.role != "student", User.is_active == True).order_by(User.full_name))  # noqa: E712
    return [{"user_id": str(u.id), "name": u.full_name or u.email, "email": u.email, "department": u.department}
            for u in users]


@router.get("/{import_id}")
def get_timetable(import_id: UUID, current_user: User = Depends(require_coordinator), db: Session = Depends(get_session)):
    imp = _get(db, import_id)
    d = timetable_service.diff(db, imp)
    return {
        **_summary(db, imp),
        "header_raw": json.loads(imp.header_raw or "{}"),
        "legend": json.loads(imp.legend or "[]"),
        "extraction_notes": json.loads(imp.extraction_notes or "[]"),
        "entries": [_entry(db, e) for e in timetable_service.entries(db, imp)],
        "diff": None if d is None else {
            "published_import_id": d["published_import_id"], "published_version": d["published_version"],
            "added": [_entry(db, e) for e in d["added"]], "removed": [_entry(db, e) for e in d["removed"]],
            "changed": [{"before": _entry(db, a), "after": _entry(db, b)} for a, b in d["changed"]],
            "unchanged": d["unchanged"],
        },
    }


@router.get("/{import_id}/source")
def get_source(import_id: UUID, current_user: User = Depends(require_coordinator), db: Session = Depends(get_session)):
    imp = _get(db, import_id)
    src = db.get(TimetableSource, imp.id)
    if not src:
        raise HTTPException(status_code=404, detail="Source file not stored")
    return Response(content=src.data, media_type=src.content_type,
                    headers={"Content-Disposition": f'inline; filename="{imp.source_filename}"'})


@router.get("/{import_id}/suggestions")
def get_suggestions(import_id: UUID, current_user: User = Depends(require_coordinator), db: Session = Depends(get_session)):
    return timetable_service.suggestions(db, _get(db, import_id))


@router.patch("/{import_id}")
def update_header(import_id: UUID, req: HeaderUpdate, current_user: User = Depends(require_coordinator),
                  db: Session = Depends(get_session)):
    try:
        imp = timetable_service.update_header(db, _get(db, import_id), req.model_dump(exclude_unset=True))
    except TimetableError as e:
        _fail(e)
    return _summary(db, imp)


@router.post("/{import_id}/reextract", status_code=202)
def reextract(import_id: UUID, current_user: User = Depends(require_coordinator), db: Session = Depends(get_session)):
    imp = _get(db, import_id)
    if imp.status not in ("draft", "failed"):
        raise HTTPException(status_code=400, detail="Only drafts can be read again")
    imp.status = "extracting"
    db.add(imp)
    db.commit()
    from app.core.celery import process_timetable_task
    process_timetable_task.delay(str(imp.id))
    return _summary(db, imp)


@router.post("/{import_id}/entries", status_code=201)
def add_entry(import_id: UUID, req: EntryFields, current_user: User = Depends(require_coordinator),
              db: Session = Depends(get_session)):
    try:
        e = timetable_service.add_entry(db, _get(db, import_id), req.model_dump(exclude_unset=True))
    except TimetableError as err:
        _fail(err)
    return _entry(db, e)


@router.patch("/{import_id}/entries/{entry_id}")
def update_entry(import_id: UUID, entry_id: UUID, req: EntryFields, current_user: User = Depends(require_coordinator),
                 db: Session = Depends(get_session)):
    imp = _get(db, import_id)
    try:
        e = timetable_service.update_entry(db, imp, _get_entry(db, imp, entry_id), req.model_dump(exclude_unset=True))
    except TimetableError as err:
        _fail(err)
    return _entry(db, e)


@router.delete("/{import_id}/entries/{entry_id}", status_code=204)
def delete_entry(import_id: UUID, entry_id: UUID, current_user: User = Depends(require_coordinator),
                 db: Session = Depends(get_session)):
    imp = _get(db, import_id)
    try:
        timetable_service.delete_entry(db, imp, _get_entry(db, imp, entry_id))
    except TimetableError as err:
        _fail(err)


@router.post("/{import_id}/publish")
def publish(import_id: UUID, req: PublishRequest, current_user: User = Depends(require_coordinator),
            db: Session = Depends(get_session)):
    try:
        return timetable_service.publish(db, current_user, _get(db, import_id), req.acknowledge_warnings)
    except TimetableError as e:
        _fail(e)


@router.post("/{import_id}/discard", status_code=204)
def discard(import_id: UUID, current_user: User = Depends(require_coordinator), db: Session = Depends(get_session)):
    try:
        timetable_service.discard(db, current_user, _get(db, import_id))
    except TimetableError as e:
        _fail(e)
