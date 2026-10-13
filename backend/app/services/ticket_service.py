"""
Help-desk ticket service — AI-assisted, human-approved.

A ticket is raised by a student (or staff member). On creation it is:
  1. triaged — category, priority and the owning office (from institution.yaml),
     by the LLM when available, otherwise by a deterministic keyword classifier
     (ported from the DJSCE student-chatbot mini-project's category matcher);
  2. drafted — the RAG assistant writes a suggested reply grounded in indexed
     knowledge, with its sources, visible to staff only.
A staff member reviews/edits the draft and sends the reply. The AI never replies
to the requester directly, and every step is written to the audit log.
"""
import json
from datetime import datetime, timezone
from typing import Any, Optional
from uuid import UUID

import structlog
from sqlmodel import Session, select

from app.core.institution_config import HelpdeskCategory, get_institution_config
from app.models.structured import Ticket, User
from app.services.audit_service import audit_service
from app.services.llm_service import llm_service
from app.services.rag_service import rag_service

log = structlog.get_logger()

TICKET_STATUSES = {"open", "answered", "closed"}
PRIORITIES = ("low", "normal", "high")
_URGENT_WORDS = ("urgent", "asap", "immediately", "deadline today", "tomorrow", "exam tomorrow", "cannot access")

_FALLBACK_CATEGORY = HelpdeskCategory(key="general", label="General Enquiry", routed_to="Help Desk")

_TRIAGE_SYSTEM = (
    "You triage help-desk tickets for a college. Choose exactly one category key from the "
    "list, a priority (low/normal/high — high only for time-critical or access-blocking "
    "issues), and give a one-sentence rationale. Never invent categories."
)


def _categories() -> list[HelpdeskCategory]:
    return get_institution_config().helpdesk_categories or [_FALLBACK_CATEGORY]


def _category(key: str) -> HelpdeskCategory:
    return next((c for c in _categories() if c.key == key), None) or next(
        (c for c in _categories() if c.key == "general"), _FALLBACK_CATEGORY
    )


class TicketService:
    # ── Triage ──────────────────────────────────────────────────────────────
    @staticmethod
    def keyword_triage(text: str) -> dict[str, Any]:
        """Deterministic classifier: score each category by keyword hits (offline fallback)."""
        lowered = text.lower()
        scores = {c.key: sum(1 for k in c.keywords if k in lowered) for c in _categories()}
        best = max(scores, key=scores.get) if scores else "general"
        key = best if scores.get(best) else "general"
        priority = "high" if any(w in lowered for w in _URGENT_WORDS) else "normal"
        return {
            "category": key,
            "priority": priority,
            "method": "keyword",
            "rationale": f"Matched {scores.get(key, 0)} keyword(s) for '{_category(key).label}'.",
        }

    def llm_triage(self, text: str) -> Optional[dict[str, Any]]:
        if not llm_service.is_available:
            return None
        listing = "\n".join(f"- {c.key}: {c.label}" for c in _categories())
        result = llm_service.complete_json(
            _TRIAGE_SYSTEM,
            f"Categories:\n{listing}\n\nReturn JSON "
            '{"category": "<key>", "priority": "low|normal|high", "rationale": "..."}'
            f"\n\n--- TICKET ---\n{text[:4000]}",
            max_tokens=300,
            default=None,
        )
        if not isinstance(result, dict):
            return None
        keys = {c.key for c in _categories()}
        category = str(result.get("category") or "").strip().lower()
        if category not in keys:
            return None  # an unknown label is a failed triage, not a new category
        priority = str(result.get("priority") or "normal").strip().lower()
        return {
            "category": category,
            "priority": priority if priority in PRIORITIES else "normal",
            "method": "llm",
            "rationale": str(result.get("rationale") or "").strip() or None,
        }

    def triage(self, text: str) -> dict[str, Any]:
        """Run the classifier chain: LLM → keyword fallback."""
        try:
            result = self.llm_triage(text)
        except Exception as e:  # noqa: BLE001 - triage must never block ticket creation
            log.warning("LLM triage failed", error=str(e))
            result = None
        return result or self.keyword_triage(text)

    def _apply_triage(self, ticket: Ticket) -> None:
        t = self.triage(f"{ticket.subject}\n\n{ticket.description}")
        ticket.category = t["category"]
        ticket.priority = t["priority"]
        ticket.routed_to = _category(t["category"]).routed_to
        ticket.triage_method = t["method"]
        ticket.triage_rationale = t["rationale"]

    def _apply_draft(self, ticket: Ticket) -> None:
        """Staff-only suggested reply grounded in all knowledge (staff review before sending)."""
        try:
            result = rag_service.answer(
                f"{ticket.subject}\n{ticket.description}", public_only=False, purpose="ticket_draft"
            )
            ticket.ai_draft_reply = result["answer"]
            ticket.ai_sources = json.dumps(result["sources"])
        except Exception as e:  # noqa: BLE001
            log.warning("Ticket draft generation failed", ticket_id=str(ticket.id), error=str(e))

    # ── Lifecycle ───────────────────────────────────────────────────────────
    def create(self, db: Session, user: User, subject: str, description: str) -> Ticket:
        ticket = Ticket(raised_by_user_id=user.id, subject=subject, description=description)
        self._apply_triage(ticket)
        self._apply_draft(ticket)
        db.add(ticket)
        db.commit()
        db.refresh(ticket)
        audit_service.record(
            db, actor=user.email, action="ticket_create", target_id=str(ticket.id),
            metadata={"category": ticket.category, "priority": ticket.priority, "triage": ticket.triage_method},
        )
        return ticket

    def retriage(self, db: Session, ticket: Ticket, actor: str) -> Ticket:
        self._apply_triage(ticket)
        self._apply_draft(ticket)
        return self._save(db, ticket, actor, "ticket_retriage", {"category": ticket.category})

    def reply(self, db: Session, ticket: Ticket, staff: User, text: str, *, close: bool = False) -> Ticket:
        ticket.reply = text
        ticket.replied_by_user_id = staff.id
        ticket.replied_at = datetime.now(timezone.utc)
        ticket.status = "closed" if close else "answered"
        used_draft = bool(ticket.ai_draft_reply) and text.strip() == ticket.ai_draft_reply.strip()
        return self._save(db, ticket, staff.email, "ticket_reply", {"used_ai_draft_verbatim": used_draft})

    def set_status(self, db: Session, ticket: Ticket, status: str, actor: str) -> Ticket:
        if status not in TICKET_STATUSES:
            raise ValueError(f"Invalid ticket status '{status}'. Allowed: {sorted(TICKET_STATUSES)}")
        ticket.status = status
        return self._save(db, ticket, actor, "ticket_status", {"status": status})

    def _save(self, db: Session, ticket: Ticket, actor: str, action: str, meta: dict) -> Ticket:
        ticket.updated_at = datetime.now(timezone.utc)
        db.add(ticket)
        db.commit()
        db.refresh(ticket)
        audit_service.record(db, actor=actor, action=action, target_id=str(ticket.id), metadata=meta)
        return ticket

    # ── Queries ─────────────────────────────────────────────────────────────
    def get(self, db: Session, ticket_id: UUID) -> Optional[Ticket]:
        return db.get(Ticket, ticket_id)

    def for_user(self, db: Session, user_id: UUID) -> list[Ticket]:
        return list(db.exec(
            select(Ticket).where(Ticket.raised_by_user_id == user_id).order_by(Ticket.created_at.desc())
        ))

    def queue(self, db: Session, *, status: Optional[str] = None, category: Optional[str] = None) -> list[Ticket]:
        stmt = select(Ticket).order_by(Ticket.created_at.desc())
        if status:
            stmt = stmt.where(Ticket.status == status)
        if category:
            stmt = stmt.where(Ticket.category == category)
        return list(db.exec(stmt))


ticket_service = TicketService()
