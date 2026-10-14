"""
Procedure (SOP / "skill") API.

Staff read procedures within their department scope; students read only approved,
student-facing ones (plain summary, never internal steps). Coordinators extract, create,
edit, approve, reject (with a reason) and retire. Every approved version is kept.
"""
import json
from datetime import datetime
from typing import Any, Optional
from uuid import UUID

import structlog
from fastapi import APIRouter, Depends, HTTPException, Query, Response
from pydantic import BaseModel, Field
from sqlmodel import Session, select

from app.api.v1.auth import department_scope, get_current_user, require_role, require_staff
from app.core.db import get_session
from app.models.structured import Employee, Skill, User
from app.services.audit_service import audit_service
from app.services.employee_service import employee_service
from app.services.procedure_service import ProcedureError, procedure_service
from app.services.skill_service import skill_service

log = structlog.get_logger()
router = APIRouter()

STATUS_LABELS = {"draft": "Draft · in review", "approved": "Approved", "stale": "Needs review",
                 "deprecated": "Retired", "rejected": "Rejected"}


class SkillEdit(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    trigger: Optional[str] = None
    escalation: Optional[str] = None
    preconditions: Optional[list[str]] = None
    steps: Optional[list[str]] = None
    decision_rules: Optional[list[str]] = None
    guardrails: Optional[list[str]] = None
    # Governance settings
    owner_office: Optional[str] = None
    owner_user_id: Optional[str] = None
    visibility: Optional[str] = None
    department: Optional[str] = None
    category: Optional[str] = None
    student_summary: Optional[str] = None
    review_by: Optional[datetime] = None


class SkillCreate(SkillEdit):
    name: str = Field(min_length=1, max_length=200)
    steps: list[str] = Field(default_factory=list)


class ApproveRequest(BaseModel):
    owner_office: Optional[str] = None
    review_by: Optional[datetime] = None


class RejectRequest(BaseModel):
    reason: str = Field(default="", max_length=1000)


class FeedbackRequest(BaseModel):
    agent_id: Optional[str] = None  # automated callers identify themselves; people are taken from the token
    outcome: str  # helpful / wrong  (agents: success / failure / escalated)
    detail: Optional[str] = None


_CONTENT_FIELDS = {"name", "description", "trigger", "escalation", "preconditions", "steps", "decision_rules", "guardrails"}


def _owner_name(db: Session, skill: Skill) -> Optional[str]:
    emp = db.get(Employee, skill.owner_employee_id) if skill.owner_employee_id else None
    return emp.display_name if emp else None


def _meta(skill: Skill, db: Optional[Session] = None) -> dict[str, Any]:
    return {
        "id": str(skill.id),
        "name": skill.name,
        "description": skill.description,
        "trigger": skill.trigger,
        "status": skill.status,
        "status_label": STATUS_LABELS.get(skill.status, skill.status),
        "version": skill.version,
        "owner_employee_id": str(skill.owner_employee_id) if skill.owner_employee_id else None,
        "owner_name": _owner_name(db, skill) if db else None,
        "owner_office": skill.owner_office,
        "review_by": skill.review_by.isoformat() if skill.review_by else None,
        "approved_by": skill.approved_by,
        "approved_at": skill.approved_at.isoformat() if skill.approved_at else None,
        "visibility": skill.visibility,
        "department": skill.department,
        "category": skill.category,
        "origin": skill.origin,
        "use_count": skill.use_count,
        "stale_reason": skill.stale_reason,
        "reject_reason": skill.reject_reason,
        "last_verified_at": skill.last_verified_at.isoformat() if skill.last_verified_at else None,
        "updated_at": skill.updated_at.isoformat(),
    }


def _full(skill: Skill, db: Optional[Session] = None) -> dict[str, Any]:
    def _list(raw: str) -> list[str]:
        try:
            return json.loads(raw or "[]")
        except json.JSONDecodeError:
            return []

    return {
        **_meta(skill, db),
        "preconditions": _list(skill.preconditions),
        "steps": _list(skill.steps),
        "decision_rules": _list(skill.decision_rules),
        "guardrails": _list(skill.guardrails),
        "escalation": skill.escalation,
        "student_summary": skill.student_summary,
        "stale_evidence": _list(skill.stale_evidence),
    }


def _get_or_404(db: Session, skill_id: str, user: Optional[User] = None) -> Skill:
    try:
        sid = UUID(skill_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid skill id")
    skill = skill_service.get(db, sid)
    scope = department_scope(user) if user else None
    if not skill or (scope is not None and skill.department not in scope):
        raise HTTPException(status_code=404, detail="Skill not found")
    return skill


def _apply_owner(db: Session, skill: Skill, owner_user_id: Optional[str]) -> None:
    if not owner_user_id:
        return
    try:
        owner = db.get(User, UUID(owner_user_id))
    except ValueError:
        owner = None
    if not owner or owner.role == "student":
        raise HTTPException(status_code=400, detail="The owner must be a staff member")
    skill.owner_employee_id = employee_service.get_or_create_for_user(db, owner).id


# ── reading ─────────────────────────────────────────────────────────────────
@router.get("")
def list_skills(
    status: Optional[str] = None,
    q: Optional[str] = None,
    category: Optional[str] = None,
    current_user: User = Depends(require_staff),
    db: Session = Depends(get_session),
):
    scope = department_scope(current_user)
    out = []
    for s in skill_service.list_skills(db, status=status):
        if scope is not None and s.department not in scope:
            continue
        if category and s.category != category:
            continue
        if q and q.strip().lower() not in f"{s.name} {s.description} {s.owner_office or ''}".lower():
            continue
        out.append(_meta(s, db))
    return out


@router.get("/student")
def student_procedures(current_user: User = Depends(get_current_user), db: Session = Depends(get_session)):
    """Approved, student-facing procedures in the caller's scope: name + plain summary only."""
    scope = department_scope(current_user)
    rows = db.exec(select(Skill).where(Skill.status == "approved", Skill.visibility == "public"))
    return [
        {"id": str(s.id), "name": s.name, "summary": s.student_summary, "owner_office": s.owner_office,
         "category": s.category, "version": s.version,
         "approved_at": s.approved_at.isoformat() if s.approved_at else None}
        for s in rows if (scope is None or s.department in scope) and (s.student_summary or "").strip()
    ]


@router.get("/handbook")
def handbook(
    format: str = Query("pdf", pattern="^(docx|pdf)$"),
    current_user: User = Depends(require_staff),
    db: Session = Depends(get_session),
):
    """Every approved procedure in the caller's scope as one document."""
    scope = department_scope(current_user)
    skills = [s for s in skill_service.list_skills(db, status="approved") if scope is None or s.department in scope]
    if not skills:
        raise HTTPException(status_code=404, detail="No approved procedures yet")
    skills.sort(key=lambda s: (s.category or "~", s.name))
    title = "Handbook of approved procedures"
    body = procedure_service.to_pdf(skills, title) if format == "pdf" else procedure_service.to_docx(skills, title)
    audit_service.record(db, actor=current_user.email, action="skill_handbook_export", metadata={"count": len(skills)})
    media = "application/pdf" if format == "pdf" else "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    return Response(content=body, media_type=media,
                    headers={"Content-Disposition": f'attachment; filename="Procedures_Handbook.{format}"'})


@router.post("/extract", status_code=202)
def trigger_extraction(current_user: User = Depends(require_role("manager")), db: Session = Depends(get_session)):
    """Run procedure extraction over accumulated fragments (synchronous for review)."""
    created = skill_service.extract_candidates(db)
    audit_service.record(db, actor=current_user.email, action="extract", metadata={"created": created})
    return {"candidates_created": created}


@router.post("", status_code=201)
def create_skill(req: SkillCreate, current_user: User = Depends(require_role("manager")), db: Session = Depends(get_session)):
    """Write a procedure by hand; it starts as a draft and goes through the same review."""
    try:
        skill = procedure_service.create_manual(db, req.model_dump(), current_user.email)
        _apply_owner(db, skill, req.owner_user_id)
        db.add(skill)
        db.commit()
    except ProcedureError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return _full(skill, db)


@router.get("/{skill_id}")
def get_skill(skill_id: str, current_user: User = Depends(require_staff), db: Session = Depends(get_session)):
    skill = _get_or_404(db, skill_id, current_user)
    return {**_full(skill, db), "citations": skill_service.citations(db, skill.id),
            "feedback": procedure_service.feedback_counts(db, skill)}


@router.get("/{skill_id}/versions")
def get_versions(skill_id: str, current_user: User = Depends(require_staff), db: Session = Depends(get_session)):
    skill = _get_or_404(db, skill_id, current_user)
    return {"current": {"version": skill.version, "status": skill.status},
            "versions": procedure_service.versions(db, skill)}


@router.get("/{skill_id}/file")
def get_skill_file(skill_id: str, current_user: User = Depends(require_staff), db: Session = Depends(get_session)):
    """Rendered SKILL.md. Only approved skills export by default (FR6)."""
    skill = _get_or_404(db, skill_id, current_user)
    if skill.status != "approved":
        raise HTTPException(status_code=409,
                            detail=f"Skill is '{skill.status}', not approved. Only approved skills are exported.")
    audit_service.record(db, actor=current_user.email, action="skill_fetch", target_id=str(skill.id),
                         metadata={"version": skill.version})
    return Response(content=skill_service.render_file(skill), media_type="text/markdown")


@router.get("/{skill_id}/export")
def export_skill(
    skill_id: str,
    format: str = Query("pdf", pattern="^(docx|pdf)$"),
    current_user: User = Depends(require_staff),
    db: Session = Depends(get_session),
):
    skill = _get_or_404(db, skill_id, current_user)
    body = procedure_service.to_pdf([skill], skill.name) if format == "pdf" else procedure_service.to_docx([skill], skill.name)
    slug = "".join(ch if ch.isalnum() else "_" for ch in skill.name).strip("_")[:60]
    media = "application/pdf" if format == "pdf" else "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    return Response(content=body, media_type=media,
                    headers={"Content-Disposition": f'attachment; filename="SOP_{slug}_v{skill.version}.{format}"'})


# ── review lifecycle ────────────────────────────────────────────────────────
@router.patch("/{skill_id}")
def edit_skill(
    skill_id: str, edit: SkillEdit,
    current_user: User = Depends(require_role("manager")), db: Session = Depends(get_session),
):
    """Edit content or settings. Changing the content of an approved procedure opens a new pending version."""
    skill = _get_or_404(db, skill_id, current_user)
    fields = edit.model_dump(exclude_none=True)
    try:
        if _CONTENT_FIELDS & set(fields):
            skill = procedure_service.start_revision(db, skill)
        skill = skill_service.update_fields(db, skill.id, {k: v for k, v in fields.items() if k in _CONTENT_FIELDS})
        procedure_service.apply_settings(skill, fields)
        _apply_owner(db, skill, edit.owner_user_id)
        db.add(skill)
        db.commit()
        db.refresh(skill)
        if skill.status == "approved":
            procedure_service.publish(db, skill)  # settings changed: refresh visibility / department of the copy
    except ProcedureError as e:
        raise HTTPException(status_code=400, detail=str(e))
    audit_service.record(db, actor=current_user.email, action="skill_edit", target_id=skill_id,
                         metadata={"fields": sorted(fields)})
    return _full(skill, db)


@router.post("/{skill_id}/approve")
def approve_skill(
    skill_id: str, req: Optional[ApproveRequest] = None,
    current_user: User = Depends(require_role("manager")), db: Session = Depends(get_session),
):
    skill = _get_or_404(db, skill_id, current_user)
    if not skill.owner_employee_id:
        skill.owner_employee_id = employee_service.get_or_create_for_user(db, current_user).id
    try:
        updated = procedure_service.approve(
            db, skill, current_user.full_name or current_user.email,
            owner_office=req.owner_office if req else None, review_by=req.review_by if req else None,
        )
    except ProcedureError as e:
        raise HTTPException(status_code=400, detail=str(e))
    audit_service.record(db, actor=current_user.email, action="approve", target_id=skill_id,
                         metadata={"version": updated.version})
    return _meta(updated, db)


@router.post("/{skill_id}/reject")
def reject_skill(
    skill_id: str, req: Optional[RejectRequest] = None,
    current_user: User = Depends(require_role("manager")), db: Session = Depends(get_session),
):
    skill = _get_or_404(db, skill_id, current_user)
    try:
        updated = procedure_service.reject(db, skill, current_user.email, req.reason if req else "")
    except ProcedureError as e:
        raise HTTPException(status_code=400, detail=str(e))
    audit_service.record(db, actor=current_user.email, action="reject", target_id=skill_id,
                         metadata={"reason": updated.reject_reason})
    return _meta(updated, db)


@router.post("/{skill_id}/retire")
def retire_skill(skill_id: str, current_user: User = Depends(require_role("manager")), db: Session = Depends(get_session)):
    skill = _get_or_404(db, skill_id, current_user)
    updated = procedure_service.retire(db, skill, current_user.email)
    audit_service.record(db, actor=current_user.email, action="skill_retire", target_id=skill_id)
    return _meta(updated, db)


@router.post("/{skill_id}/feedback")
def skill_feedback(
    skill_id: str, req: FeedbackRequest,
    current_user: User = Depends(require_staff), db: Session = Depends(get_session),
):
    """Helpful / wrong (people) or an execution outcome (agents). Repeated "wrong" flags it for review."""
    skill = _get_or_404(db, skill_id, current_user)
    audit_service.record(
        db, actor=req.agent_id or current_user.email, action="skill_use", target_id=str(skill.id),
        metadata={"outcome": req.outcome, "detail": req.detail, "version": skill.version},
    )
    flagged = procedure_service.after_feedback(db, skill)
    if flagged:
        from app.services.fragment_service import fragment_service

        fragment_service.delete_for_skill(db, skill.id)
    return {"status": "recorded", "skill_id": str(skill.id), "outcome": req.outcome, "flagged_for_review": flagged,
            "feedback": procedure_service.feedback_counts(db, skill)}
