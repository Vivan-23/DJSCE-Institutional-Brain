"""Tests for the skill pipeline: extraction, lifecycle, file export, feedback, RBAC."""
import json
from unittest.mock import patch

from sqlmodel import select

from app.models.structured import AuditLog, Fragment, Skill, SkillCitation, User
from tests.helpers import register


def _register(client, email, role="employee"):
    return register(client, email, "Skill User", role)


def _make_manager(db, email):
    user = db.exec(select(User).where(User.email == email)).first()
    user.role = "manager"
    db.add(user)
    db.commit()


def _seed_skill(db, status="draft", name="Handle refund request"):
    skill = Skill(
        name=name,
        description="How refunds are processed",
        trigger="A customer requests a refund",
        preconditions=json.dumps(["Order exists"]),
        steps=json.dumps(["Verify the order", "Issue the refund"]),
        decision_rules=json.dumps(["If amount > $500, escalate to a manager"]),
        guardrails=json.dumps(["Refunds over $500 require manager approval"]),
        escalation="Escalate to the support lead",
        status=status,
    )
    db.add(skill)
    db.commit()
    db.refresh(skill)
    return skill


_CANNED_SKILL = {
    "name": "Handle a refund",
    "description": "Process a customer refund request",
    "trigger": "customer requests a refund",
    "preconditions": ["order exists"],
    "steps": ["verify order", "issue refund"],
    "decision_rules": ["if amount > 500 escalate to manager"],
    "guardrails": ["refunds over 500 require manager approval"],
    "escalation": "manager",
}


class TestSkillExtraction:
    def test_extract_clusters_and_cites(self, db_session):
        from app.services.skill_service import skill_service

        content = (
            "Refund process: when a customer requests a refund over 500 dollars "
            "escalate to a manager for approval before issuing."
        )
        for _ in range(4):
            db_session.add(Fragment(source_type="transcript", content=content))
        db_session.commit()

        with patch(
            "app.services.skill_service.extraction_service.extract_skill",
            return_value=_CANNED_SKILL,
        ):
            created = skill_service.extract_candidates(db_session)
        assert created >= 1

        skill = db_session.exec(
            select(Skill).where(Skill.name == "Handle a refund")
        ).first()
        assert skill is not None and skill.status == "draft"
        cites = db_session.exec(
            select(SkillCitation).where(SkillCitation.skill_id == skill.id)
        ).all()
        assert len(cites) >= 3  # citation coverage back to evidence

    def test_one_candidate_per_source(self, db_session):
        """Overlapping vocabulary across sources must not collapse them into one skill."""
        from app.services.skill_service import skill_service

        shared = "procedure approval committee department faculty students submit form within days"
        for ref in ("sop_exam.txt", "sop_lab.txt", "Meeting A"):
            db_session.add(Fragment(source_type="document", source_ref=ref, content=f"{ref}: {shared}"))
        db_session.commit()
        with patch("app.services.skill_service.extraction_service.extract_skill", return_value=_CANNED_SKILL):
            created = skill_service.extract_candidates(db_session)
        assert created == 3

    def test_render_file_contains_sections(self):
        from app.services.skill_service import skill_service

        skill = Skill(
            name="Handle refund request",
            description="How refunds are processed",
            trigger="A customer requests a refund",
            preconditions=json.dumps(["Order exists"]),
            steps=json.dumps(["Verify the order", "Issue the refund"]),
            decision_rules=json.dumps(["If amount > $500, escalate"]),
            guardrails=json.dumps(["Over $500 needs approval"]),
            escalation="Support lead",
            status="approved",
        )
        rendered = skill_service.render_file(skill)
        assert "# Handle refund request" in rendered
        assert "## Steps" in rendered
        assert "1. Verify the order" in rendered
        assert "## Guardrails" in rendered
        assert "## Escalation" in rendered


class TestSkillAPI:
    def test_list_requires_auth(self, client):
        assert client.get("/api/v1/skills").status_code == 401

    def test_extract_requires_manager(self, client):
        token = _register(client, "skill-emp@test.com")
        res = client.post("/api/v1/skills/extract", headers={"Authorization": f"Bearer {token}"})
        assert res.status_code == 403

    def test_get_skill_returns_full_with_citations(self, client, db_session):
        token = _register(client, "skill-get@test.com")
        skill = _seed_skill(db_session, name="Onboard a new hire")
        res = client.get(
            f"/api/v1/skills/{skill.id}", headers={"Authorization": f"Bearer {token}"}
        )
        assert res.status_code == 200
        body = res.json()
        assert body["name"] == "Onboard a new hire"
        assert body["steps"] == ["Verify the order", "Issue the refund"]
        assert "citations" in body

    def test_file_requires_approved_then_exports(self, client, db_session):
        email = "skill-file@test.com"
        token = _register(client, email)
        skill = _seed_skill(db_session, status="draft", name="Refund flow file")
        auth = {"Authorization": f"Bearer {token}"}

        # Draft skills are not exported.
        assert client.get(f"/api/v1/skills/{skill.id}/file", headers=auth).status_code == 409

        # Approve (requires manager) then export.
        _make_manager(db_session, email)
        approve = client.post(f"/api/v1/skills/{skill.id}/approve", headers=auth)
        assert approve.status_code == 200
        assert approve.json()["status"] == "approved"

        res = client.get(f"/api/v1/skills/{skill.id}/file", headers=auth)
        assert res.status_code == 200
        assert res.headers["content-type"].startswith("text/markdown")
        assert "# Refund flow file" in res.text

    def test_feedback_records_audit(self, client, db_session):
        token = _register(client, "skill-fb@test.com")
        skill = _seed_skill(db_session, status="approved", name="Incident response")
        res = client.post(
            f"/api/v1/skills/{skill.id}/feedback",
            json={"agent_id": "agent-007", "outcome": "success", "detail": "completed"},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert res.status_code == 200
        logs = db_session.exec(
            select(AuditLog).where(AuditLog.action == "skill_use")
        ).all()
        assert any(l.actor == "agent-007" and l.target_id == str(skill.id) for l in logs)
