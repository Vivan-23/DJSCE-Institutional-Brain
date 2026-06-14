"""Audit API — the trail of extraction, approval, agent skill-use, and PA actions."""
import json
from typing import Optional

from fastapi import APIRouter, Depends
from sqlmodel import Session

from app.api.v1.auth import require_role
from app.core.db import get_session
from app.models.structured import User
from app.services.audit_service import audit_service

router = APIRouter()


@router.get("")
def list_audit(
    action: Optional[str] = None,
    target_id: Optional[str] = None,
    limit: int = 200,
    current_user: User = Depends(require_role("manager")),
    db: Session = Depends(get_session),
):
    entries = audit_service.list_recent(db, action=action, target_id=target_id, limit=limit)
    out = []
    for e in entries:
        try:
            meta = json.loads(e.audit_metadata or "{}")
        except json.JSONDecodeError:
            meta = {}
        out.append(
            {
                "id": str(e.id),
                "actor": e.actor,
                "action": e.action,
                "target_id": e.target_id,
                "metadata": meta,
                "created_at": e.created_at.isoformat(),
            }
        )
    return out
