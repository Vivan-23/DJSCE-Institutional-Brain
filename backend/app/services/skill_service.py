"""
Skill service — the procedure layer (FR2, FR3, FR5, FR6).

Turns accumulated Fragments into structured, executable Skills:
  * cluster related fragments by topic,
  * synthesize a candidate skill via the extraction engine,
  * link every candidate back to its source fragments (citations),
  * manage the draft → approved → stale → deprecated lifecycle, and
  * render approved skills into an agent-consumable SKILL.md file.

Clustering uses a dependency-free greedy keyword-overlap pass so the pipeline is
deterministic and testable without the vector store; embeddings remain available
for retrieval elsewhere.
"""
import json
import re
from datetime import datetime, timezone
from typing import Any, Optional
from uuid import UUID

import structlog
from sqlmodel import Session, select

from app.models.structured import Fragment, Skill, SkillCitation
from app.services.extraction_service import extraction_service

log = structlog.get_logger()

# Fragment kinds that carry procedural knowledge worth synthesizing into skills.
_PROCEDURE_SOURCES = {"transcript", "document", "slack", "email", "checkin", "followup", "db"}
_MIN_CLUSTER_SIZE = 3
_MAX_CLUSTERS_PER_RUN = 5

_STOPWORDS = {
    "the", "a", "an", "and", "or", "but", "if", "then", "to", "of", "in", "on",
    "for", "with", "is", "are", "was", "were", "be", "this", "that", "it", "we",
    "i", "you", "they", "he", "she", "will", "should", "can", "do", "did", "have",
    "has", "had", "at", "by", "as", "from", "so", "our", "their", "about", "out",
}

_VALID_SKILL_STATUSES = {"draft", "approved", "stale", "deprecated", "rejected"}


class SkillService:
    # ── Extraction / clustering ─────────────────────────────────────────────
    def extract_candidates(self, db: Session) -> int:
        """Cluster un-cited procedure fragments and synthesize candidate skills."""
        cited_ids = {c.fragment_id for c in db.exec(select(SkillCitation))}
        fragments = [
            f
            for f in db.exec(select(Fragment).order_by(Fragment.created_at.desc()).limit(500))
            # Procedures are internal governance knowledge; public student FAQs are
            # answered by the assistant directly, not synthesized into procedures.
            if f.source_type in _PROCEDURE_SOURCES and f.visibility == "internal" and f.id not in cited_ids
        ]
        clusters = self._cluster(fragments)

        created = 0
        for cluster in clusters[:_MAX_CLUSTERS_PER_RUN]:
            if len(cluster) < _MIN_CLUSTER_SIZE:
                continue
            skill = self._synthesize(db, cluster)
            if skill:
                created += 1
        log.info("Skill candidates synthesized", clusters=len(clusters), created=created)
        return created

    def _synthesize(self, db: Session, cluster: list[Fragment]) -> Optional[Skill]:
        extracted = extraction_service.extract_skill([f.content for f in cluster])
        if not extracted:
            return None
        skill = self._persist_candidate(db, extracted, cluster)
        return skill

    def _persist_candidate(
        self, db: Session, extracted: dict[str, Any], cluster: list[Fragment]
    ) -> Skill:
        skill = Skill(
            name=extracted["name"],
            description=extracted.get("description", ""),
            trigger=extracted.get("trigger", ""),
            preconditions=json.dumps(extracted.get("preconditions", [])),
            steps=json.dumps(extracted.get("steps", [])),
            decision_rules=json.dumps(extracted.get("decision_rules", [])),
            guardrails=json.dumps(extracted.get("guardrails", [])),
            escalation=extracted.get("escalation"),
            status="draft",
        )
        db.add(skill)
        db.commit()
        db.refresh(skill)

        # Every candidate traces to the fragments it was synthesized from (FR2/NFR
        # citation coverage). Element-level linking is best-effort.
        for frag in cluster:
            db.add(SkillCitation(skill_id=skill.id, fragment_id=frag.id))
        db.commit()
        log.info("Candidate skill created", skill_id=str(skill.id), name=skill.name, citations=len(cluster))
        return skill

    @staticmethod
    def _cluster(fragments: list[Fragment]) -> list[list[Fragment]]:
        """Greedy keyword-overlap clustering. Deterministic, no external services."""
        def keywords(text: str) -> set[str]:
            tokens = re.findall(r"[a-z][a-z']+", text.lower())
            return {t for t in tokens if len(t) > 2 and t not in _STOPWORDS}

        items = [(f, keywords(f.content)) for f in fragments]
        clusters: list[list[Fragment]] = []
        cluster_keys: list[set[str]] = []

        for frag, kws in items:
            if not kws:
                continue
            best_idx, best_overlap = -1, 0
            for idx, ckeys in enumerate(cluster_keys):
                overlap = len(kws & ckeys)
                if overlap > best_overlap:
                    best_idx, best_overlap = idx, overlap
            # Require a meaningful keyword overlap to join an existing cluster.
            if best_idx >= 0 and best_overlap >= 2:
                clusters[best_idx].append(frag)
                cluster_keys[best_idx] |= kws
            else:
                clusters.append([frag])
                cluster_keys.append(set(kws))

        clusters.sort(key=len, reverse=True)
        return clusters

    # ── Lifecycle ───────────────────────────────────────────────────────────
    def list_skills(self, db: Session, *, status: Optional[str] = None) -> list[Skill]:
        stmt = select(Skill).order_by(Skill.updated_at.desc())
        if status:
            stmt = stmt.where(Skill.status == status)
        return list(db.exec(stmt))

    def get(self, db: Session, skill_id: UUID) -> Optional[Skill]:
        return db.get(Skill, skill_id)

    def citations(self, db: Session, skill_id: UUID) -> list[dict[str, Any]]:
        out: list[dict[str, Any]] = []
        for c in db.exec(select(SkillCitation).where(SkillCitation.skill_id == skill_id)):
            frag = db.get(Fragment, c.fragment_id)
            out.append(
                {
                    "citation_id": str(c.id),
                    "fragment_id": str(c.fragment_id),
                    "element": c.element,
                    "source_type": frag.source_type if frag else None,
                    "source_ref": frag.source_ref if frag else None,
                    "content": frag.content if frag else None,
                }
            )
        return out

    def update_fields(self, db: Session, skill_id: UUID, fields: dict[str, Any]) -> Optional[Skill]:
        skill = db.get(Skill, skill_id)
        if not skill:
            return None
        scalar = {"name", "description", "trigger", "escalation"}
        json_list = {"preconditions", "steps", "decision_rules", "guardrails"}
        for key, value in fields.items():
            if key in scalar and value is not None:
                setattr(skill, key, value)
            elif key in json_list and value is not None:
                setattr(skill, key, json.dumps(value))
        skill.updated_at = datetime.now(timezone.utc)
        db.add(skill)
        db.commit()
        db.refresh(skill)
        return skill

    def set_status(
        self,
        db: Session,
        skill_id: UUID,
        status: str,
        *,
        owner_employee_id: Optional[UUID] = None,
    ) -> Optional[Skill]:
        if status not in _VALID_SKILL_STATUSES:
            raise ValueError(f"Invalid skill status '{status}'. Allowed: {sorted(_VALID_SKILL_STATUSES)}")
        skill = db.get(Skill, skill_id)
        if not skill:
            return None
        skill.status = status
        if status == "approved":
            skill.last_verified_at = datetime.now(timezone.utc)
            if owner_employee_id:
                skill.owner_employee_id = owner_employee_id
        skill.updated_at = datetime.now(timezone.utc)
        db.add(skill)
        db.commit()
        db.refresh(skill)
        return skill

    # ── Rendering (FR6) ─────────────────────────────────────────────────────
    def render_file(self, skill: Skill) -> str:
        """Deterministic SKILL.md rendering — the agent-consumable deliverable."""
        def _list(raw: str) -> list[str]:
            try:
                return json.loads(raw or "[]")
            except json.JSONDecodeError:
                return []

        def _section(title: str, items: list[str], *, numbered: bool = False) -> str:
            if not items:
                return ""
            if numbered:
                body = "\n".join(f"{i}. {s}" for i, s in enumerate(items, 1))
            else:
                body = "\n".join(f"- {s}" for s in items)
            return f"\n## {title}\n{body}\n"

        lines = [
            "---",
            f"name: {skill.name}",
            f"status: {skill.status}",
            f"version: {skill.version}",
            f"description: {skill.description}",
            "---",
            "",
            f"# {skill.name}",
            "",
            skill.description or "",
            "",
            f"**Trigger:** {skill.trigger or 'n/a'}",
        ]
        body = "\n".join(lines)
        body += _section("Preconditions", _list(skill.preconditions))
        body += _section("Steps", _list(skill.steps), numbered=True)
        body += _section("Decision Rules", _list(skill.decision_rules))
        body += _section("Guardrails", _list(skill.guardrails))
        if skill.escalation:
            body += f"\n## Escalation\n{skill.escalation}\n"
        return body.strip() + "\n"


skill_service = SkillService()
