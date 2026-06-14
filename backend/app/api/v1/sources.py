"""Source connector API (FR1) — discover sources and sync fragments from them."""
from datetime import datetime
from typing import Optional

import structlog
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlmodel import Session

from app.api.v1.auth import get_current_user, require_role
from app.core.db import get_session
from app.models.structured import User
from app.services.connectors.base import RawFragment
from app.services.connectors.registry import all_connectors, get_connector

log = structlog.get_logger()
router = APIRouter()


class PushItem(BaseModel):
    content: str
    author: Optional[str] = None
    source_ref: Optional[str] = None
    occurred_at: Optional[datetime] = None


class SyncRequest(BaseModel):
    # Optional pushed items; when omitted the connector pulls from its source.
    items: Optional[list[PushItem]] = None


@router.get("")
def list_sources(
    current_user: User = Depends(get_current_user),
):
    return [
        {"name": c.name, "label": c.label, "configured": c.is_configured}
        for c in all_connectors()
    ]


@router.post("/{name}/sync")
def sync_source(
    name: str,
    req: SyncRequest,
    current_user: User = Depends(require_role("manager")),
    db: Session = Depends(get_session),
):
    connector = get_connector(name)
    if not connector:
        raise HTTPException(status_code=404, detail=f"Unknown connector '{name}'")

    items = None
    if req.items is not None:
        items = [
            RawFragment(
                content=i.content,
                author=i.author,
                source_ref=i.source_ref,
                occurred_at=i.occurred_at,
            )
            for i in req.items
        ]
    stored = connector.sync(db, items=items)
    return {"connector": name, "fragments_stored": stored}
