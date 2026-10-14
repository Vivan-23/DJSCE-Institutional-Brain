"""
Help-desk ticket service — AI-assisted, human-approved.

A ticket is raised by a student (or staff member). On creation it is:
  1. triaged — category, priority and the owning office (from institution.yaml),
     by a configurable chain of engines (``settings.TRIAGE_ENGINES``): the LLM, the
     optional laya classifier (fast, non-generative, calibrated probabilities) and a
     deterministic keyword classifier (ported from the DJSCE student-chatbot
     mini-project's category matcher) that always answers last;
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

from app.core.institution_config import ALL_DEPARTMENTS, HelpdeskCategory, get_institution_config
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


_LAYA_MIN_CONFIDENCE = 0.5  # below this laya abstains and the next engine decides
_laya_router = None


def _laya():
    """Lazily build laya's Router (downloads its checkpoint on first use). None if not installed."""
    global _laya_router
    if _laya_router is None:
        try:
            import laya  # optional dependency: pip install laya==0.3.21
        except ImportError:
            return None
        _laya_router = laya.Router()
    return _laya_router


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

    def laya_triage(self, text: str) -> Optional[dict[str, Any]]:
        """Non-generative triage with laya: one forward pass, a probability per category.

        Each configured category becomes an option whose criteria are its label and keywords,
        so the classifier can only ever return a configured key. Abstains (None) when laya is
        not installed or its confidence is below ``_LAYA_MIN_CONFIDENCE``.
        """
        router = _laya()
        if router is None:
            return None
        criteria = {
            c.key: f"{c.label}" + (f": {', '.join(c.keywords)}" if c.keywords else "")
            for c in _categories()
        }
        questions = {
            "category": {
                "type": "choice",
                "instructions": "Which college office should handle the student query in `message`?",
                "criteria": criteria,
            },
            "is_urgent": {
                "type": "noul",
                "instructions": "Is the student in `message` blocked or facing a deadline within a day or two?",
            },
        }
        out = router.predict({"message": text[:4000]}, questions)
        cat = (out.get("answers") or {}).get("category") or {}
        key = str(cat.get("choice") or "")
        prob = float(cat.get("answer_confidence") or 0.0)
        if key not in criteria or prob < _LAYA_MIN_CONFIDENCE:
            return None
        urgent = float(((out.get("answers") or {}).get("is_urgent") or {}).get("noul") or 0.0)
        return {
            "category": key,
            "priority": "high" if urgent >= 0.5 else "normal",
            "method": "laya",
            "rationale": f"laya: P({key}) = {prob:.2f}; P(urgent) = {urgent:.2f}.",
        }

    _ENGINES = {"llm": "llm_triage", "laya": "laya_triage"}

    def triage(self, text: str, engines: Optional[list[str]] = None) -> dict[str, Any]:
        """Run the configured engine chain; the keyword classifier always answers last."""
        from app.core.config import settings

        chain = engines if engines is not None else [
            e.strip() for e in settings.TRIAGE_ENGINES.split(",") if e.strip()
        ]
        for name in chain:
            method = self._ENGINES.get(name)
            if not method:
                continue  # "keyword" (or an unknown name) is handled by the final fallback
            try:
                result = getattr(self, method)(text)
            except Exception as e:  # noqa: BLE001 - triage must never block ticket creation
                log.warning("Triage engine failed", engine=name, error=str(e))
                result = None
            if result:
                return result
        return self.keyword_triage(text)

    def _apply_triage(self, ticket: Ticket) -> None:
        t = self.triage(f"{ticket.subject}\n\n{ticket.description}")
        ticket.category = t["category"]
        ticket.priority = t["priority"]
        ticket.routed_to = _category(t["category"]).routed_to
        ticket.triage_method = t["method"]
        ticket.triage_rationale = t["rationale"]

    def _apply_draft(self, db: Session, ticket: Ticket) -> None:
        """Staff-only suggested reply (staff review before sending), grounded in internal and
        public knowledge of the requester's department plus institution-wide material."""
        requester = db.get(User, ticket.raised_by_user_id)
        departments = [requester.department, ALL_DEPARTMENTS] if requester and requester.department else None
        try:
            result = rag_service.answer(
                f"{ticket.subject}\n{ticket.description}", public_only=False,
                departments=departments, purpose="ticket_draft",
            )
            ticket.ai_draft_reply = result["answer"]
            ticket.ai_sources = json.dumps(result["sources"])
            used = {s["skill_id"] for s in result["sources"] if s.get("skill_id")}
            if used:
                from app.services.procedure_service import procedure_service

                procedure_service.record_use(db, used)
        except Exception as e:  # noqa: BLE001
            log.warning("Ticket draft generation failed", ticket_id=str(ticket.id), error=str(e))

    # ── Lifecycle ───────────────────────────────────────────────────────────
    def create(self, db: Session, user: User, subject: str, description: str) -> Ticket:
        ticket = Ticket(raised_by_user_id=user.id, subject=subject, description=description)
        self._apply_triage(ticket)
        self._apply_draft(db, ticket)
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
        self._apply_draft(db, ticket)
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
