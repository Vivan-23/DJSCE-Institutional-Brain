from pathlib import Path

import structlog
from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile

from sqlalchemy import func
from sqlmodel import Session, select

from app.api.v1.auth import department_scope, parse_department, require_staff
from app.core.db import get_session
from app.models.structured import Fragment, User
from app.services.fragment_service import VISIBILITIES
from app.services.parser import parse_pdf, parse_docx

log = structlog.get_logger()
router = APIRouter()

MAX_FILE_BYTES = 10 * 1024 * 1024  # 10 MB
ALLOWED_EXTENSIONS = {".txt", ".pdf", ".docx"}


@router.get("/documents")
def list_documents(current_user: User = Depends(require_staff), db: Session = Depends(get_session)):
    """Uploaded documents the caller may retrieve from (one row per file), newest first."""
    q = (select(Fragment.source_ref, Fragment.visibility, Fragment.department,
                func.count(Fragment.id), func.max(Fragment.created_at))
         .where(Fragment.source_type == "document")
         .group_by(Fragment.source_ref, Fragment.visibility, Fragment.department)
         .order_by(func.max(Fragment.created_at).desc()))
    scope = department_scope(current_user)
    if scope is not None:
        q = q.where(Fragment.department.in_(scope))
    return [{"filename": ref, "visibility": vis, "department": dept, "passages": n,
             "added_at": added.isoformat() if added else None}
            for ref, vis, dept, n, added in db.exec(q)]


@router.post("/file", status_code=202)
async def ingest_file(
    file: UploadFile = File(...),
    visibility: str = Form("internal"),
    department: str = Form("all"),
    current_user: User = Depends(require_staff),
):
    """Queue a document for indexing. ``visibility="public"`` makes it answerable for students."""
    if visibility not in VISIBILITIES:
        raise HTTPException(status_code=400, detail=f"visibility must be one of {sorted(VISIBILITIES)}")
    department = parse_department(department)
    ext = Path(file.filename or "").suffix.lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file type '{ext}'. Allowed: {', '.join(ALLOWED_EXTENSIONS)}",
        )

    content = await file.read()
    if len(content) > MAX_FILE_BYTES:
        raise HTTPException(status_code=413, detail="File exceeds 10 MB limit")

    if ext == ".pdf":
        text = parse_pdf(content)
    elif ext == ".docx":
        text = parse_docx(content)
    else:
        try:
            text = content.decode("utf-8")
        except UnicodeDecodeError:
            raise HTTPException(status_code=400, detail="File is not valid UTF-8 text")

    if not text.strip():
        raise HTTPException(status_code=400, detail="File is empty or contains no extractable text")

    # Enqueue background processing — returns immediately (202 Accepted)
    from app.core.celery import process_document_task
    task = process_document_task.delay(text, file.filename, visibility, department)

    log.info("Document queued for processing", filename=file.filename, visibility=visibility,
             department=department, task_id=task.id)
    return {
        "filename": file.filename,
        "status": "queued",
        "visibility": visibility,
        "department": department,
        "task_id": task.id,
        "message": "Document is being processed in the background. Graph and embeddings will update shortly.",
    }
