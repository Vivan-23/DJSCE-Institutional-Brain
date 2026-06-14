"""
Extraction engine.

Turns raw text into structured organizational knowledge via the LLM:
  - extract_meeting(): a transcript -> summary, participants, decisions, commitments
  - (Phase 3) extract_skill(): clustered fragments -> an executable procedure

This is the procedure-aware replacement for entity-only NER. The spaCy NER
service is retained separately for graph entity enrichment.
"""
from typing import Any, Optional

import structlog

from app.services.llm_service import llm_service

log = structlog.get_logger()


_MEETING_SYSTEM = (
    "You are an expert chief-of-staff who reads meeting transcripts and extracts "
    "what matters operationally. You identify decisions made, new features or "
    "initiatives, and — most importantly — concrete commitments (action items): "
    "who agreed to do what, and by when. Capture the owner's name exactly as it "
    "appears. Only include commitments that were actually made; do not invent them."
)

_MEETING_INSTRUCTIONS = """Extract the following from the transcript and return JSON with this exact shape:
{
  "summary": "2-4 sentence neutral summary of the meeting",
  "participants": ["Name", ...],
  "decisions": ["A decision that was made", ...],
  "commitments": [
    {
      "assignee": "Person's name exactly as mentioned",
      "description": "What they committed to do (imperative, specific)",
      "due": "a due date or timeframe if stated, else null"
    }
  ]
}
If a field has no content, use an empty list. Do not include commentary."""


_SKILL_SYSTEM = (
    "You are a senior operations analyst. Given a set of evidence fragments "
    "(messages, transcript snippets, ticket resolutions, notes) about how a "
    "company handles a recurring situation, you synthesize a single executable "
    "procedure — a 'skill'. Capture conditional logic and exceptions (e.g. "
    "'if order > $500, escalate to a manager'), not just a linear checklist. "
    "Base every element strictly on the evidence; do not invent policy."
)

_SKILL_INSTRUCTIONS = """Synthesize ONE executable skill from the evidence below and return JSON with this exact shape:
{
  "name": "short imperative name (e.g. 'Handle a refund request')",
  "description": "one sentence on what this skill does and when to use it",
  "trigger": "the situation that invokes this skill",
  "preconditions": ["what must be true before acting", ...],
  "steps": ["ordered, executable action", ...],
  "decision_rules": ["branching logic / thresholds, e.g. 'if X then Y'", ...],
  "guardrails": ["hard constraints; actions that require human approval", ...],
  "escalation": "who/what to defer to when out of bounds, or null"
}
Use empty lists where there is no evidence. Do not include commentary."""


class ExtractionService:
    def extract_skill(self, fragments: list[str]) -> Optional[dict[str, Any]]:
        """Synthesize one structured skill from a cluster of evidence fragments."""
        if not llm_service.is_available:
            log.warning("LLM unavailable — skill extraction skipped")
            return None
        if not fragments:
            return None

        evidence = "\n".join(f"- {f}" for f in fragments)[:24000]
        result = llm_service.complete_json(
            _SKILL_SYSTEM,
            f"{_SKILL_INSTRUCTIONS}\n\n--- EVIDENCE ---\n{evidence}",
            max_tokens=2048,
            default=None,
        )
        return self._normalize_skill(result)

    @staticmethod
    def _normalize_skill(result: Any) -> Optional[dict[str, Any]]:
        if not isinstance(result, dict):
            return None
        name = (result.get("name") or "").strip()
        if not name:
            return None

        def _str_list(key: str) -> list[str]:
            return [s.strip() for s in (result.get(key) or []) if isinstance(s, str) and s.strip()]

        return {
            "name": name,
            "description": (result.get("description") or "").strip(),
            "trigger": (result.get("trigger") or "").strip(),
            "preconditions": _str_list("preconditions"),
            "steps": _str_list("steps"),
            "decision_rules": _str_list("decision_rules"),
            "guardrails": _str_list("guardrails"),
            "escalation": (result.get("escalation") or None) if isinstance(result.get("escalation"), str) else None,
        }

    def extract_meeting(self, transcript: str) -> dict[str, Any]:
        """Return {summary, participants, decisions, commitments} for a transcript."""
        default = {"summary": "", "participants": [], "decisions": [], "commitments": []}
        if not llm_service.is_available:
            log.warning("LLM unavailable — meeting extraction skipped")
            return default

        user_prompt = f"{_MEETING_INSTRUCTIONS}\n\n--- TRANSCRIPT ---\n{transcript[:24000]}"
        result = llm_service.complete_json(
            _MEETING_SYSTEM, user_prompt, max_tokens=2048, default=default
        )
        return self._normalize_meeting(result, default)

    @staticmethod
    def _normalize_meeting(result: Any, default: dict) -> dict[str, Any]:
        if not isinstance(result, dict):
            return default
        commitments = []
        for c in result.get("commitments") or []:
            if not isinstance(c, dict):
                continue
            desc = (c.get("description") or "").strip()
            if not desc:
                continue
            commitments.append(
                {
                    "assignee": (c.get("assignee") or "").strip() or None,
                    "description": desc,
                    "due": c.get("due") or None,
                }
            )
        return {
            "summary": (result.get("summary") or "").strip(),
            "participants": [p for p in (result.get("participants") or []) if isinstance(p, str)],
            "decisions": [d for d in (result.get("decisions") or []) if isinstance(d, str)],
            "commitments": commitments,
        }


extraction_service = ExtractionService()
