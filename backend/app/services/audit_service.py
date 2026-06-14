"""
Audit service — the immutable trail behind everything the system does on its own.

Every meaningful action (extraction, approval, skill use by an agent, PA check-in
and follow-up) is recorded as an AuditLog row. This backs FR7 (agent execution
safety) and the security requirement that every agent skill-use is logged.
"""
import json
from typing import Any, Optional

import structlog
from sqlmodel import Session, select

from app.models.structured import AuditLog

log = structlog.get_logger()


class AuditService:
    def record(
        self,
        db: Session,
        *,
        actor: str,
        action: str,
        target_id: Optional[str] = None,
        metadata: Optional[dict[str, Any]] = None,
    ) -> AuditLog:
        """Append an audit entry. ``actor`` is an employee email or an agent id."""
        entry = AuditLog(
            actor=actor,
            action=action,
            target_id=str(target_id) if target_id is not None else None,
            audit_metadata=json.dumps(metadata or {}, default=str),
        )
        db.add(entry)
        db.commit()
        db.refresh(entry)
        log.info("Audit recorded", actor=actor, action=action, target_id=entry.target_id)
        return entry

    def list_recent(
        self,
        db: Session,
        *,
        action: Optional[str] = None,
        target_id: Optional[str] = None,
        limit: int = 200,
    ) -> list[AuditLog]:
        stmt = select(AuditLog).order_by(AuditLog.created_at.desc())
        if action:
            stmt = stmt.where(AuditLog.action == action)
        if target_id:
            stmt = stmt.where(AuditLog.target_id == str(target_id))
        return list(db.exec(stmt.limit(limit)))


audit_service = AuditService()
