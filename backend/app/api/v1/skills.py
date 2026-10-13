"""
Skill API — the deliverable surface (FR5 review, FR6 export, FR7 safety).

Read/list/file/feedback are available to any authenticated principal (agents
included). Mutating the review lifecycle (approve/reject/edit/extract) requires
an elevated role.
"""
import json
from typing import Any, Optional
from uuid import UUID

import structlog
from fastapi import APIRouter, Depends, HTTPException, Response
from pydantic import BaseModel
from sqlmodel import Session

from app.api.v1.auth import require_role, require_staff
from app.core.db import get_session
from app.models.structured import Skill, User
from app.services.audit_service import audit_service
from app.services.employee_service import employee_service
from app.services.skill_service import skill_service

log = structlog.get_logger()
router = APIRouter()


class SkillEdit(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    trigger: Optional[str] = None
    escalation: Optional[str] = None
    preconditions: Optional[list[str]] = None
    steps: Optional[list[str]] = None
    decision_rules: Optional[list[str]] = None
    guardrails: Optional[list[str]] = None


class FeedbackRequest(BaseModel):
    agent_id: str
    outcome: str  # success / failure / escalated
    detail: Optional[str] = None


def _meta(skill: Skill) -> dict[str, Any]:
    return {
        "id": str(skill.id),
        "name": skill.name,
        "description": skill.description,
        "trigger": skill.trigger,
        "status": skill.status,
        "version": skill.version,
        "owner_employee_id": str(skill.owner_employee_id) if skill.owner_employee_id else None,
        "last_verified_at": skill.last_verified_at.isoformat() if skill.last_verified_at else None,
        "updated_at": skill.updated_at.isoformat(),
    }


def _full(skill: Skill) -> dict[str, Any]:
    def _list(raw: str) -> list[str]:
        try:
            return json.loads(raw or "[]")
        except json.JSONDecodeError:
            return []

    return {
        **_meta(skill),
        "preconditions": _list(skill.preconditions),
        "steps": _list(skill.steps),
        "decision_rules": _list(skill.decision_rules),
        "guardrails": _list(skill.guardrails),
        "escalation": skill.escalation,
    }


def _get_or_404(db: Session, skill_id: str) -> Skill:
    try:
        sid = UUID(skill_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid skill id")
    skill = skill_service.get(db, sid)
    if not skill:
        raise HTTPException(status_code=404, detail="Skill not found")
    return skill


@router.get("")
def list_skills(
    status: Optional[str] = None,
    current_user: User = Depends(require_staff),
    db: Session = Depends(get_session),
):
    return [_meta(s) for s in skill_service.list_skills(db, status=status)]


@router.post("/extract", status_code=202)
def trigger_extraction(
    current_user: User = Depends(require_role("manager")),
    db: Session = Depends(get_session),
):
    """Run procedure extraction over accumulated fragments (synchronous for review)."""
    created = skill_service.extract_candidates(db)
    audit_service.record(db, actor=current_user.email, action="extract", metadata={"created": created})
    return {"candidates_created": created}


@router.get("/{skill_id}")
def get_skill(
    skill_id: str,
    current_user: User = Depends(require_staff),
    db: Session = Depends(get_session),
):
    skill = _get_or_404(db, skill_id)
    return {**_full(skill), "citations": skill_service.citations(db, skill.id)}


@router.get("/{skill_id}/file")
def get_skill_file(
    skill_id: str,
    current_user: User = Depends(require_staff),
    db: Session = Depends(get_session),
):
    """Rendered, agent-consumable skill file. Only approved skills export by default (FR6)."""
    skill = _get_or_404(db, skill_id)
    if skill.status != "approved":
        raise HTTPException(
            status_code=409,
            detail=f"Skill is '{skill.status}', not approved. Only approved skills are exported.",
        )
    audit_service.record(
        db, actor=current_user.email, action="skill_fetch", target_id=str(skill.id),
        metadata={"version": skill.version},
    )
    return Response(content=skill_service.render_file(skill), media_type="text/markdown")


@router.patch("/{skill_id}")
def edit_skill(
    skill_id: str,
    edit: SkillEdit,
    current_user: User = Depends(require_role("manager")),
    db: Session = Depends(get_session),
):
    skill = _get_or_404(db, skill_id)
    updated = skill_service.update_fields(db, skill.id, edit.model_dump(exclude_none=True))
    audit_service.record(db, actor=current_user.email, action="skill_edit", target_id=skill_id)
    return _full(updated)


@router.post("/{skill_id}/approve")
def approve_skill(
    skill_id: str,
    current_user: User = Depends(require_role("manager")),
    db: Session = Depends(get_session),
):
    skill = _get_or_404(db, skill_id)
    owner = employee_service.get_or_create_for_user(db, current_user)
    updated = skill_service.set_status(db, skill.id, "approved", owner_employee_id=owner.id)
    audit_service.record(db, actor=current_user.email, action="approve", target_id=skill_id)
    return _meta(updated)


@router.post("/{skill_id}/reject")
def reject_skill(
    skill_id: str,
    current_user: User = Depends(require_role("manager")),
    db: Session = Depends(get_session),
):
    skill = _get_or_404(db, skill_id)
    updated = skill_service.set_status(db, skill.id, "rejected")
    audit_service.record(db, actor=current_user.email, action="reject", target_id=skill_id)
    return _meta(updated)


@router.post("/{skill_id}/feedback")
def skill_feedback(
    skill_id: str,
    req: FeedbackRequest,
    current_user: User = Depends(require_staff),
    db: Session = Depends(get_session),
):
    """An agent reports an execution outcome (FR7) — logged and fed to freshness."""
    skill = _get_or_404(db, skill_id)
    audit_service.record(
        db,
        actor=req.agent_id,
        action="skill_use",
        target_id=str(skill.id),
        metadata={"outcome": req.outcome, "detail": req.detail, "version": skill.version},
    )
    return {"status": "recorded", "skill_id": str(skill.id), "outcome": req.outcome}
