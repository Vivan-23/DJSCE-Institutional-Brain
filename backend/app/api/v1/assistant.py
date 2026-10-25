"""The one assistant box: questions, work updates and "my classes" from a single message (assistant_service)."""
from typing import Any, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlmodel import Session

from app.api.v1.auth import get_current_user, require_staff
from app.core.db import get_session
from app.models.structured import QueryLog, User
from app.services.assistant_service import assistant_service

router = APIRouter()


class AssistantMessage(BaseModel):
    text: str = Field(max_length=4000)


class UndoRequest(BaseModel):
    commitment_id: UUID
    before: Optional[dict[str, Any]] = None
    new: bool = False


@router.post("/message")
def message(req: AssistantMessage, current_user: User = Depends(get_current_user), db: Session = Depends(get_session)):
    text = req.text.strip()
    if not text:
        raise HTTPException(status_code=400, detail="Please type a message")
    out = assistant_service.handle(db, current_user, text)
    if out["plan"]["question"]:
        db.add(QueryLog(question=out["plan"]["question"][:500], role=current_user.role,
                        department=current_user.department, source_count=len(out["sources"])))
        db.commit()
    return out


@router.post("/undo")
def undo(req: UndoRequest, current_user: User = Depends(require_staff), db: Session = Depends(get_session)):
    try:
        return assistant_service.undo(db, current_user, req.commitment_id, req.before, req.new)
    except LookupError:
        raise HTTPException(status_code=404, detail="Task not found")
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
