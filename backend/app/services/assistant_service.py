"""One assistant box: work out what a message is asking for, then hand it to the feature that already does it.

- a work update ("finished the C31 marks, BIA paper half done") → the check-in extraction (``pa_service``),
  which updates the person's tasks; every change carries its previous state so the person can undo it;
- a question about college knowledge → grounded answers (``rag_service``), cited;
- a question about their own teaching timetable → the published schedule (``schedule_service``).

One message can be several of these. Routing uses one small model call and falls back to keyword rules, so
the box keeps working without the language model. Students only get answers (public knowledge); nothing they
type changes data.
"""
from __future__ import annotations

import re
from datetime import date, datetime, timedelta, timezone
from typing import Any, Optional
from uuid import UUID

import structlog
from sqlmodel import Session

from app.models.structured import Commitment, CommitmentUpdate, User
from app.services.audit_service import audit_service
from app.services.llm_service import llm_service

log = structlog.get_logger()

_UPDATE_WORDS = re.compile(
    r"\b(finished|completed|complete[d]? the|done with|did|submitted|uploaded|sent|checked|corrected|graded|"
    r"working on|started|halfway|half done|stuck|blocked|waiting (for|on)|couldn'?t|could not|pending|"
    r"will finish|progress|today i|i have|i've)\b", re.I)
_QUESTION_START = re.compile(
    r"^\s*(what|when|where|who|whom|which|why|how|is|are|can|could|do|does|did|should|will|tell me|show|list|"
    r"give me|explain|find)\b", re.I)
_SCHEDULE_WORDS = re.compile(r"\b(class(es)?|lectures?|labs?|timetable|schedule|teach(ing)?|free period)\b", re.I)
_MY_WORDS = re.compile(r"\b(my|i|me)\b", re.I)

_ROUTER_SYSTEM = (
    "You route messages a college faculty member types into one assistant box. Reply with JSON only:\n"
    '{"update": bool, "question": str|null, "schedule": null|"today"|"tomorrow"|"week"|"YYYY-MM-DD"}\n'
    "- update: true if they report progress on their own work (finished, started, half done, stuck, submitted...).\n"
    "- question: the question part rewritten as a standalone question, if they ask about college rules, procedures,\n"
    "  dates, committees, documents or anything else to look up; null otherwise. Not for their own classes.\n"
    "- schedule: set when they ask about their own classes/lectures/timetable, with the day they mean; else null.\n"
    "A message can have several parts. Greetings or thanks alone: all false/null."
)


def route(text: str, *, staff: bool, today: Optional[date] = None) -> dict[str, Any]:
    """Which features a message needs: ``{"update": bool, "question": str|None, "schedule": str|None}``."""
    if not staff:
        return {"update": False, "question": text, "schedule": None}
    plan: Optional[dict[str, Any]] = None
    if llm_service.is_available:
        result = llm_service.complete_json(_ROUTER_SYSTEM, text, max_tokens=200, default=None)
        if isinstance(result, dict):
            plan = {
                "update": bool(result.get("update")),
                "question": (result.get("question") or "").strip() or None,
                "schedule": _schedule_day(result.get("schedule")),
            }
    if plan is None:
        plan = _keyword_route(text)
    if not (plan["update"] or plan["question"] or plan["schedule"]):
        # Nothing recognised: treat it as a question rather than silently doing nothing.
        plan["question"] = text
    return plan


def _schedule_day(value: Any) -> Optional[str]:
    if value in ("today", "tomorrow", "week"):
        return value
    if isinstance(value, str) and re.fullmatch(r"\d{4}-\d{2}-\d{2}", value):
        return value
    return None


def _keyword_route(text: str) -> dict[str, Any]:
    is_question = text.strip().endswith("?") or bool(_QUESTION_START.match(text))
    schedule = None
    if is_question and _SCHEDULE_WORDS.search(text) and _MY_WORDS.search(text):
        low = text.lower()
        schedule = "tomorrow" if "tomorrow" in low else "week" if "week" in low else "today"
    return {
        "update": bool(_UPDATE_WORDS.search(text)) and not (is_question and not re.search(r"[.!]\s", text)),
        "question": text if is_question and not schedule else None,
        "schedule": schedule,
    }


def _snapshot(c: Commitment) -> dict[str, Any]:
    return {"status": c.status, "progress": c.progress, "remaining": c.remaining,
            "blocked_reason": c.blocked_reason,
            "marked_done_at": c.marked_done_at.isoformat() if c.marked_done_at else None}


class AssistantService:
    def handle(self, db: Session, user: User, text: str) -> dict[str, Any]:
        from app.api.v1.auth import department_scope, is_staff
        from app.services.schedule_service import local_today

        staff = is_staff(user)
        plan = route(text, staff=staff)
        log.info("assistant.route", user=user.email, update=plan["update"], question=bool(plan["question"]),
                 schedule=plan["schedule"])
        parts: list[str] = []
        out: dict[str, Any] = {"updates": [], "sources": [], "schedule": None, "plan": plan}

        if plan["update"] and staff:
            reply, updates = self._apply_update(db, user, text)
            out["updates"] = updates
            parts.append(reply)

        if plan["schedule"] and staff:
            sched_text, sched = self._schedule(db, user, plan["schedule"], local_today())
            out["schedule"] = sched
            parts.append(sched_text)

        if plan["question"]:
            from app.services.rag_service import rag_service

            try:
                result = rag_service.answer(plan["question"], public_only=not staff, departments=department_scope(user))
                parts.append(result["answer"])
                out["sources"] = result["sources"]
            except Exception as e:  # keep the rest of the reply if only the lookup fails
                log.error("assistant.rag_failed", user=user.email, error=str(e))
                parts.append("I couldn't look that up just now. Please try asking again in a moment.")

        out["reply"] = "\n\n".join(p for p in parts if p) or "Noted."
        return out

    # ── work updates ────────────────────────────────────────────────────────
    def _apply_update(self, db: Session, user: User, text: str) -> tuple[str, list[dict[str, Any]]]:
        from app.services.commitment_service import commitment_service
        from app.services.employee_service import employee_service
        from app.services.pa_service import pa_service

        employee = employee_service.get_or_create_for_user(db, user)
        before = {str(c.id): _snapshot(c) for c in commitment_service.for_employee(db, employee.id, open_only=True)}
        checkin = pa_service.get_today_checkin(db, employee)
        result = pa_service.checkin_message(db, employee, checkin, text)
        updates = []
        for u in result.get("updates") or []:
            u = dict(u)
            u["before"] = None if u.get("new") else before.get(u["commitment_id"])
            if u.get("new") and not u.get("description"):
                c = db.get(Commitment, UUID(u["commitment_id"]))
                u["description"] = c.description if c else None
            updates.append(u)
        if not updates:
            return ("I've noted that in today's check-in, but I couldn't match it to one of your tasks. "
                    "You can update a task directly on My Work."), []
        return result.get("reply") or "Your tasks are updated.", updates

    def undo(self, db: Session, user: User, commitment_id: UUID, before: Optional[dict[str, Any]], new: bool) -> dict:
        """Put one of the caller's tasks back as it was before an assistant update (or drop one it created)."""
        from app.services.employee_service import employee_service

        employee = employee_service.get_or_create_for_user(db, user)
        c = db.get(Commitment, commitment_id)
        if not c or c.assignee_employee_id != employee.id:
            raise LookupError("Task not found")
        if new:
            c.status = "dropped"
            summary = "Removed (assistant created it by mistake)"
        else:
            if not isinstance(before, dict) or "status" not in before:
                raise ValueError("Nothing to undo")
            c.status = before["status"]
            c.progress = max(0, min(100, int(before.get("progress") or 0)))
            c.remaining = before.get("remaining")
            c.blocked_reason = before.get("blocked_reason")
            done_at = before.get("marked_done_at")
            c.marked_done_at = datetime.fromisoformat(done_at) if done_at else None
            summary = "Assistant update undone"
        db.add(CommitmentUpdate(commitment_id=c.id, raw_text=summary, structured_summary=summary,
                                status_change=c.status, progress=c.progress, actor=employee.display_name,
                                source="undo"))
        db.add(c)
        db.commit()
        db.refresh(c)
        audit_service.record(db, actor=user.email, action="assistant_update_undone", target_id=str(c.id),
                             metadata={"new": new})
        return {"commitment_id": str(c.id), "description": c.description, "status": c.status, "progress": c.progress}

    # ── own timetable ───────────────────────────────────────────────────────
    def _schedule(self, db: Session, user: User, when: str, today: date) -> tuple[str, dict[str, Any]]:
        from app.services.schedule_service import schedule_service

        if when == "week":
            start, days, label = today, 7, "in the next 7 days"
        elif when == "tomorrow":
            start, days, label = today + timedelta(days=1), 1, "tomorrow"
        elif when == "today":
            start, days, label = today, 1, "today"
        else:
            start, days = date.fromisoformat(when), 1
            label = f"on {start.strftime('%A %d %B')}"
        items = schedule_service.occurrences(db, user, start, days)
        if not schedule_service.published_entries(db, user.id):
            return ("No teaching timetable has been published for you yet.",
                    {"start": start.isoformat(), "days": days, "items": []})
        teaching = [i for i in items if i["status"] not in ("cancelled", "holiday")]
        if not teaching:
            text = f"You have no classes {label}."
        else:
            lines = []
            for i in teaching:
                when_txt = f"{i['start_time']}-{i['end_time']}" if i.get("end_time") else (i.get("start_time") or "")
                day_txt = f"{date.fromisoformat(i['date']).strftime('%a')} " if days > 1 else ""
                where = ", ".join(x for x in (i.get("class_label"), f"room {i['room']}" if i.get("room") else None) if x)
                lines.append(f"- {day_txt}{when_txt}: {i.get('subject') or 'Class'}{f' ({where})' if where else ''}")
            text = f"Your classes {label}:\n" + "\n".join(lines)
        return text, {"start": start.isoformat(), "days": days, "items": items}


assistant_service = AssistantService()
