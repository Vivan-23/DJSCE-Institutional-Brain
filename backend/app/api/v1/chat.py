import structlog
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlmodel import Session

from app.api.v1.auth import department_scope, get_current_user, is_staff
from app.core.db import get_session
from app.models.structured import QueryLog, User
from app.services.rag_service import rag_service

log = structlog.get_logger()
router = APIRouter()


class ChatMessage(BaseModel):
    role: str
    content: str


class ChatRequest(BaseModel):
    messages: list[ChatMessage]


@router.post("")
@router.post("/")
def chat_endpoint(
    request: ChatRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_session),
):
    """Grounded Q&A. Students are answered from public knowledge only."""
    if not request.messages:
        raise HTTPException(status_code=422, detail="Messages list cannot be empty")

    user_query = request.messages[-1].content.strip()
    if not user_query:
        raise HTTPException(status_code=422, detail="Last message content cannot be empty")

    public_only = not is_staff(current_user)
    log.info("Chat query received", user=current_user.email, public_only=public_only, query_len=len(user_query))

    try:
        result = rag_service.answer(
            user_query, public_only=public_only, departments=department_scope(current_user)
        )
    except Exception as e:
        log.error("RAG query failed", user=current_user.email, error=str(e))
        raise HTTPException(
            status_code=502,
            detail="The knowledge assistant is temporarily unavailable. Please try again.",
        )

    db.add(QueryLog(question=user_query[:500], role=current_user.role, department=current_user.department,
                    source_count=len(result["sources"])))
    db.commit()
    return {"response": result["answer"], "sources": result["sources"], "scope": "public" if public_only else "all",
            "departments": department_scope(current_user)}
