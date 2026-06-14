"""
Company PA service — the active capture loop (FR1c).

Each employee has a personal assistant that:
  * generates natural-language follow-ups grounded in their open/overdue
    commitments (never a form);
  * runs a short end-of-day check-in where the employee just *talks* about their
    day, and the PA turns that into structured CommitmentUpdates + Fragments.

Everything the PA captures is written back to the knowledge base (Fragments,
CommitmentUpdates) so procedure extraction and freshness stay fed.

The PA degrades gracefully without an LLM: follow-ups fall back to a plain
template, and a check-in still records the employee's words as a Fragment.
"""
import json
from datetime import datetime, timezone
from typing import Any, Optional
from uuid import UUID

import structlog
from sqlmodel import Session, select

from app.models.structured import CheckIn, Commitment, Employee
from app.services.audit_service import audit_service
from app.services.commitment_service import commitment_service, VALID_STATUSES
from app.services.fragment_service import fragment_service
from app.services.llm_service import llm_service

log = structlog.get_logger()


_FOLLOWUP_SYSTEM = (
    "You are a helpful, warm executive assistant checking in with a colleague. "
    "You write a SINGLE short, natural follow-up message about one of their open "
    "commitments — like a friendly nudge from a teammate, not a status form. "
    "One or two sentences, conversational, no preamble, no sign-off."
)

_CHECKIN_OPENER = (
    "Hey! Wrapping up for the day — how did things go? Just tell me what you "
    "worked on and I'll keep your commitments up to date."
)

_CHECKIN_SYSTEM = (
    "You are an employee's personal AI assistant running a relaxed end-of-day "
    "check-in. The employee describes their day in their own words. Your job: "
    "(1) reply like a supportive colleague in 1-3 sentences, and (2) map what "
    "they said onto their tracked commitments, proposing status changes and short "
    "summaries, plus any brand-new commitments they mention. Never invent progress "
    "they didn't describe."
)


def _checkin_instructions(commitments: list[Commitment]) -> str:
    listing = (
        "\n".join(f'- id={c.id} | "{c.description}" (status: {c.status})' for c in commitments)
        or "(no open commitments on record)"
    )
    return f"""The employee's currently open commitments:
{listing}

Return JSON with this exact shape:
{{
  "reply": "your short, friendly reply to the employee",
  "updates": [
    {{
      "commitment_id": "the id from the list above this update refers to",
      "status": "one of open/in_progress/blocked/done/dropped, or null if unchanged",
      "summary": "one-line summary of the progress they described"
    }}
  ],
  "new_commitments": [
    {{ "description": "a new action item they mentioned that isn't in the list" }}
  ]
}}
Only include updates for commitments they actually talked about. Use [] when empty."""


class PAService:
    # ── Proactive follow-ups ────────────────────────────────────────────────
    def pending_followups(self, db: Session, employee: Employee) -> list[dict[str, Any]]:
        """Natural-language nudges for this employee's stale open commitments."""
        stale = [
            c
            for c in commitment_service.needs_followup(db)
            if c.assignee_employee_id == employee.id
        ]
        followups: list[dict[str, Any]] = []
        for c in stale:
            followups.append(
                {
                    "commitment_id": str(c.id),
                    "description": c.description,
                    "status": c.status,
                    "due_date": c.due_date.isoformat() if c.due_date else None,
                    "message": self._followup_message(c),
                }
            )
        return followups

    def _followup_message(self, commitment: Commitment) -> str:
        fallback = (
            f"Quick check-in — how's \"{commitment.description}\" coming along? "
            "Anything blocking it?"
        )
        if not llm_service.is_available:
            return fallback
        try:
            msg = llm_service.complete(
                _FOLLOWUP_SYSTEM,
                f'Commitment: "{commitment.description}" (current status: {commitment.status}). '
                "Write the follow-up message.",
                max_tokens=120,
                temperature=0.6,
            ).strip()
            return msg or fallback
        except Exception as e:  # pragma: no cover - defensive
            log.warning("Follow-up generation failed", error=str(e))
            return fallback

    def record_followup_reply(
        self, db: Session, employee: Employee, commitment_id: UUID, text: str
    ) -> Optional[dict[str, Any]]:
        """Capture an employee's reply to a follow-up: update + fragment + audit."""
        commitment = db.get(Commitment, commitment_id)
        if not commitment or commitment.assignee_employee_id != employee.id:
            return None

        status_change, summary = self._interpret_reply(commitment, text)
        commitment_service.record_update(
            db,
            commitment_id,
            raw_text=text,
            structured_summary=summary,
            status_change=status_change,
            source="followup",
        )
        fragment_service.create_fragment(
            db,
            source_type="followup",
            content=text,
            author_employee_id=employee.id,
            occurred_at=datetime.now(timezone.utc),
        )
        audit_service.record(
            db,
            actor=employee.display_name,
            action="followup",
            target_id=str(commitment_id),
            metadata={"status_change": status_change},
        )
        db.refresh(commitment)
        return {
            "commitment_id": str(commitment.id),
            "status": commitment.status,
            "summary": summary,
            "acknowledgement": "Thanks — got it, I've updated that for you.",
        }

    def _interpret_reply(
        self, commitment: Commitment, text: str
    ) -> tuple[Optional[str], Optional[str]]:
        """Infer a status change + summary from a free-text follow-up reply."""
        if not llm_service.is_available:
            return None, text[:200]
        result = llm_service.complete_json(
            "You interpret a short status reply about one task. Return JSON "
            '{"status": one of open/in_progress/blocked/done/dropped or null, '
            '"summary": "one-line summary"}.',
            f'Task: "{commitment.description}" (current status {commitment.status}).\n'
            f"Employee reply: {text}",
            max_tokens=200,
            default={},
        )
        status = result.get("status") if isinstance(result, dict) else None
        if status not in VALID_STATUSES:
            status = None
        summary = (result.get("summary") if isinstance(result, dict) else None) or text[:200]
        return status, summary

    # ── End-of-day check-in ─────────────────────────────────────────────────
    def get_today_checkin(self, db: Session, employee: Employee) -> CheckIn:
        """Return today's check-in for the employee, creating it (with an opener) if new."""
        today = datetime.now(timezone.utc).date()
        for ci in db.exec(select(CheckIn).where(CheckIn.employee_id == employee.id)):
            ci_date = ci.date.date() if isinstance(ci.date, datetime) else ci.date
            if ci_date == today:
                return ci

        checkin = CheckIn(
            employee_id=employee.id,
            date=datetime.now(timezone.utc),
            conversation=json.dumps([{"role": "assistant", "content": _CHECKIN_OPENER}]),
            extracted_updates="[]",
        )
        db.add(checkin)
        db.commit()
        db.refresh(checkin)
        return checkin

    def checkin_message(
        self, db: Session, employee: Employee, checkin: CheckIn, text: str
    ) -> dict[str, Any]:
        """Process one employee turn: reply, extract structured updates, write back."""
        conversation = _load(checkin.conversation, [])
        conversation.append({"role": "user", "content": text})

        open_commitments = commitment_service.for_employee(db, employee.id, open_only=True)
        parsed = self._extract_checkin(open_commitments, text)
        reply = parsed.get("reply") or "Thanks for the update!"

        applied = self._apply_checkin_updates(db, employee, open_commitments, parsed)

        # Always preserve the employee's own words as a fragment.
        fragment_service.create_fragment(
            db,
            source_type="checkin",
            content=text,
            author_employee_id=employee.id,
            occurred_at=datetime.now(timezone.utc),
        )

        conversation.append({"role": "assistant", "content": reply})
        existing_updates = _load(checkin.extracted_updates, [])
        existing_updates.extend(applied)
        checkin.conversation = json.dumps(conversation)
        checkin.extracted_updates = json.dumps(existing_updates, default=str)
        db.add(checkin)
        db.commit()
        db.refresh(checkin)

        audit_service.record(
            db,
            actor=employee.display_name,
            action="checkin",
            target_id=str(checkin.id),
            metadata={"updates_applied": len(applied)},
        )
        return {"reply": reply, "updates": applied}

    def _extract_checkin(
        self, commitments: list[Commitment], text: str
    ) -> dict[str, Any]:
        default = {"reply": "Thanks — noted!", "updates": [], "new_commitments": []}
        if not llm_service.is_available:
            return default
        result = llm_service.complete_json(
            _CHECKIN_SYSTEM,
            _checkin_instructions(commitments) + f"\n\n--- EMPLOYEE ---\n{text}",
            max_tokens=1024,
            default=default,
        )
        return result if isinstance(result, dict) else default

    def _apply_checkin_updates(
        self,
        db: Session,
        employee: Employee,
        open_commitments: list[Commitment],
        parsed: dict[str, Any],
    ) -> list[dict[str, Any]]:
        valid_ids = {str(c.id) for c in open_commitments}
        applied: list[dict[str, Any]] = []

        for upd in parsed.get("updates") or []:
            if not isinstance(upd, dict):
                continue
            cid = str(upd.get("commitment_id") or "")
            if cid not in valid_ids:
                continue
            status = upd.get("status")
            if status not in VALID_STATUSES:
                status = None
            summary = (upd.get("summary") or "").strip() or None
            commitment_service.record_update(
                db,
                UUID(cid),
                raw_text=summary or "(check-in)",
                structured_summary=summary,
                status_change=status,
                source="checkin",
            )
            applied.append({"commitment_id": cid, "status": status, "summary": summary})

        # New commitments the employee surfaced during the check-in.
        new_items = [
            {"description": (n.get("description") or "").strip(), "assignee": employee.display_name}
            for n in (parsed.get("new_commitments") or [])
            if isinstance(n, dict) and (n.get("description") or "").strip()
        ]
        for item in new_items:
            created = Commitment(
                assignee_employee_id=employee.id,
                description=item["description"],
                status="open",
                confidence=0.6,
            )
            db.add(created)
            db.commit()
            db.refresh(created)
            applied.append(
                {"commitment_id": str(created.id), "status": "open", "summary": "new commitment", "new": True}
            )
        return applied

    def complete_checkin(self, db: Session, checkin: CheckIn) -> CheckIn:
        checkin.completed = True
        db.add(checkin)
        db.commit()
        db.refresh(checkin)
        return checkin


def _load(raw: Optional[str], default: Any) -> Any:
    try:
        return json.loads(raw) if raw else default
    except (json.JSONDecodeError, TypeError):
        return default


pa_service = PAService()
