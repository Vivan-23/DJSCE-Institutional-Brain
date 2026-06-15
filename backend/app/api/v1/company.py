"""Company branding — non-sensitive identity for the frontend (name + logo badge)."""
from fastapi import APIRouter

from app.core.company_config import get_company_config

router = APIRouter()


@router.get("")
def get_company():
    """Public branding pulled from company.yaml. No auth (login page reads it too)."""
    cfg = get_company_config()
    return {"name": cfg.name, "short_code": cfg.short_code}
