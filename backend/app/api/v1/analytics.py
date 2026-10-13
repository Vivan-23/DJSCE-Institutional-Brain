"""Coordinator analytics dashboard data."""
from fastapi import APIRouter, Depends, Query
from sqlmodel import Session

from app.api.v1.auth import require_role
from app.core.db import get_session
from app.models.structured import User
from app.services.analytics_service import analytics_service

router = APIRouter()


@router.get("")
def analytics(
    days: int = Query(30, ge=1, le=365),
    current_user: User = Depends(require_role("manager")),
    db: Session = Depends(get_session),
):
    """Commitments per committee, ticket resolution times, most-asked questions (last ``days``)."""
    return analytics_service.summary(db, days=days)
