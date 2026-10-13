"""Institution branding — non-sensitive identity for the frontend (name + logo badge)."""
from fastapi import APIRouter

from app.core.institution_config import get_institution_config

router = APIRouter()


@router.get("")
def get_institution():
    """Public branding pulled from institution.yaml. No auth (login page reads it too)."""
    cfg = get_institution_config()
    return {"name": cfg.name, "short_code": cfg.short_code, "full_name": cfg.full_name}
