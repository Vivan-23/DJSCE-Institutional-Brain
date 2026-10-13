from pathlib import Path

import structlog
from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile

from app.api.v1.auth import require_staff
from app.models.structured import User
from app.services.fragment_service import VISIBILITIES
from app.services.parser import parse_pdf, parse_docx

log = structlog.get_logger()
router = APIRouter()

MAX_FILE_BYTES = 10 * 1024 * 1024  # 10 MB
ALLOWED_EXTENSIONS = {".txt", ".pdf", ".docx"}


@router.post("/file", status_code=202)
async def ingest_file(
    file: UploadFile = File(...),
    visibility: str = Form("internal"),
    current_user: User = Depends(require_staff),
):
    """Queue a document for indexing. ``visibility="public"`` makes it answerable for students."""
    if visibility not in VISIBILITIES:
        raise HTTPException(status_code=400, detail=f"visibility must be one of {sorted(VISIBILITIES)}")
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
    task = process_document_task.delay(text, file.filename, visibility)

    log.info("Document queued for processing", filename=file.filename, visibility=visibility, task_id=task.id)
    return {
        "filename": file.filename,
        "status": "queued",
        "visibility": visibility,
        "task_id": task.id,
        "message": "Document is being processed in the background. Graph and embeddings will update shortly.",
    }
