"""
Freshness engine (FR4) — keeps approved skills current.

On a schedule (and on new evidence) it compares recent fragments against each
approved skill. When new evidence *contradicts* a skill, the skill is flagged
``stale`` and its owner is notified via an ActiveInsight. Skills are never
silently rewritten — a stale flag routes the skill back through human review.
"""
import json
from datetime import datetime, timezone
from typing import Any
from uuid import UUID

import structlog
from sqlmodel import Session, select

from app.models.structured import ActiveInsight, Fragment, Skill, SkillCitation
from app.services.audit_service import audit_service
from app.services.llm_service import llm_service

log = structlog.get_logger()

_RECENT_FRAGMENTS = 60

_CONTRADICTION_SYSTEM = (
    "You are a meticulous compliance reviewer. You are given an existing approved "
    "procedure and some recent evidence from company activity. Decide whether the "
    "new evidence CONTRADICTS the procedure (a rule, threshold, step, or owner has "
    "changed or is now done differently). Mere new detail is not a contradiction."
)


class FreshnessService:
    def scan(self, db: Session) -> int:
        """Flag approved skills whose evidence now contradicts them. Returns count flagged."""
        approved = list(db.exec(select(Skill).where(Skill.status == "approved")))
        if not approved:
            return 0

        recent = list(
            db.exec(select(Fragment).order_by(Fragment.created_at.desc()).limit(_RECENT_FRAGMENTS))
        )
        flagged = 0
        for skill in approved:
            evidence = self._new_evidence(db, skill, recent)
            if not evidence:
                continue
            verdict = self._detect_contradiction(skill, evidence)
            if verdict.get("contradicts"):
                self._flag_stale(db, skill, verdict.get("reason", "New evidence contradicts this skill."), evidence)
                flagged += 1
        log.info("Freshness scan complete", approved=len(approved), flagged=flagged)
        return flagged

    @staticmethod
    def _new_evidence(db: Session, skill: Skill, recent: list[Fragment]) -> list[Fragment]:
        """Recent fragments not already cited by the skill and newer than its last verification."""
        cited = {
            c.fragment_id for c in db.exec(select(SkillCitation).where(SkillCitation.skill_id == skill.id))
        }
        cutoff = skill.last_verified_at or skill.created_at
        if cutoff and cutoff.tzinfo is None:
            cutoff = cutoff.replace(tzinfo=timezone.utc)
        out: list[Fragment] = []
        for f in recent:
            if f.id in cited or f.source_type == "procedure":  # a procedure's own copy is not new evidence
                continue
            occurred = f.occurred_at or f.created_at
            if occurred and occurred.tzinfo is None:
                occurred = occurred.replace(tzinfo=timezone.utc)
            if cutoff and occurred and occurred <= cutoff:
                continue
            out.append(f)
        return out[:20]

    def _detect_contradiction(self, skill: Skill, evidence: list[Fragment]) -> dict[str, Any]:
        default = {"contradicts": False, "reason": ""}
        if not llm_service.is_available:
            return default
        rules = json.loads(skill.decision_rules or "[]")
        steps = json.loads(skill.steps or "[]")
        guardrails = json.loads(skill.guardrails or "[]")
        skill_text = (
            f"Procedure: {skill.name}\nDescription: {skill.description}\n"
            f"Steps: {steps}\nDecision rules: {rules}\nGuardrails: {guardrails}"
        )
        evidence_text = "\n".join(f"- {f.content}" for f in evidence)[:8000]
        result = llm_service.complete_json(
            _CONTRADICTION_SYSTEM,
            "Return JSON {\"contradicts\": true/false, \"reason\": \"short explanation\"}.\n\n"
            f"--- EXISTING PROCEDURE ---\n{skill_text}\n\n--- RECENT EVIDENCE ---\n{evidence_text}",
            max_tokens=400,
            default=default,
        )
        return result if isinstance(result, dict) else default

    def _flag_stale(self, db: Session, skill: Skill, reason: str, evidence: list[Fragment] = ()) -> None:
        skill.status = "stale"
        skill.stale_reason = reason
        skill.stale_evidence = json.dumps(
            [{"source_ref": f.source_ref, "source_type": f.source_type, "content": f.content[:500]} for f in evidence][:5]
        )
        skill.updated_at = datetime.now(timezone.utc)
        db.add(skill)
        # A procedure under review must not be cited as approved.
        from app.services.fragment_service import fragment_service

        fragment_service.delete_for_skill(db, skill.id)
        insight = ActiveInsight(
            category="freshness",
            observation=f"Skill '{skill.name}' may be out of date: {reason}",
            impact_rationale="Agents executing a stale procedure can act on outdated rules. Re-verify before further use.",
            suggested_actions=json.dumps(
                ["Review the contradicting evidence", "Re-extract the skill", "Re-approve or deprecate"]
            ),
            confidence_score=0.7,
        )
        db.add(insight)
        db.commit()
        audit_service.record(
            db,
            actor="freshness",
            action="skill_stale",
            target_id=str(skill.id),
            metadata={"reason": reason},
        )
        log.info("Skill flagged stale", skill_id=str(skill.id), reason=reason)


freshness_service = FreshnessService()
