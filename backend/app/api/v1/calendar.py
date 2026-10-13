"""Academic calendar + personal deadlines for the signed-in user."""
from fastapi import APIRouter, Depends, Query
from sqlmodel import Session

from app.api.v1.auth import department_scope, get_current_user, is_staff
from app.core.db import get_session
from app.core.institution_config import get_institution_config
from app.models.structured import User
from app.services.calendar_service import SOON_DAYS, calendar_service

router = APIRouter()


@router.get("")
def upcoming(
    days: int = Query(60, ge=1, le=366),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_session),
):
    """Dates from today to ``today + days`` (overdue commitments included), soonest first."""
    items = calendar_service.upcoming(
        db, current_user, staff=is_staff(current_user), departments=department_scope(current_user), days=days
    )
    return {"note": get_institution_config().calendar_note, "soon_days": SOON_DAYS, "items": items}
