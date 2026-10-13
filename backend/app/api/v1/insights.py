import structlog
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, select

from app.api.v1.auth import require_staff
from app.core.db import get_session
from app.models.structured import ActiveInsight, User

log = structlog.get_logger()
router = APIRouter()


@router.get("")
@router.get("/")
def get_insights(
    db: Session = Depends(get_session),
    current_user: User = Depends(require_staff),
):
    insights = db.exec(
        select(ActiveInsight).where(ActiveInsight.is_dismissed == False)  # noqa: E712
    ).all()
    return insights


@router.post("/{insight_id}/dismiss")
def dismiss_insight(
    insight_id: str,
    db: Session = Depends(get_session),
    current_user: User = Depends(require_staff),
):
    try:
        uid = UUID(insight_id)
    except ValueError:
        raise HTTPException(status_code=422, detail="Invalid insight ID format")

    insight = db.get(ActiveInsight, uid)
    if not insight:
        raise HTTPException(status_code=404, detail="Insight not found")

    insight.is_dismissed = True
    db.add(insight)
    db.commit()
    log.info("Insight dismissed", insight_id=insight_id, user=current_user.email)
    return {"status": "dismissed", "id": insight_id}


@router.delete("/{insight_id}")
def delete_insight(
    insight_id: str,
    db: Session = Depends(get_session),
    current_user: User = Depends(require_staff),
):
    try:
        uid = UUID(insight_id)
    except ValueError:
        raise HTTPException(status_code=422, detail="Invalid insight ID format")

    insight = db.get(ActiveInsight, uid)
    if not insight:
        raise HTTPException(status_code=404, detail="Insight not found")

    db.delete(insight)
    db.commit()
    return {"status": "deleted", "id": insight_id}
