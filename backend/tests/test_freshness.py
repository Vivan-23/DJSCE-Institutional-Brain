"""Tests for the freshness engine — contradiction detection flags skills stale."""
import json
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch

from sqlmodel import select

from app.models.structured import ActiveInsight, AuditLog, Fragment, Skill


def _approved_skill(db, name, *, verified_days_ago=10):
    skill = Skill(
        name=name,
        description="A procedure",
        trigger="something happens",
        steps=json.dumps(["do a thing"]),
        decision_rules=json.dumps(["if X then Y"]),
        guardrails=json.dumps(["never do Z"]),
        status="approved",
        last_verified_at=datetime.now(timezone.utc) - timedelta(days=verified_days_ago),
    )
    db.add(skill)
    db.commit()
    db.refresh(skill)
    return skill


def _recent_fragment(db, content):
    f = Fragment(source_type="slack", content=content, occurred_at=datetime.now(timezone.utc))
    db.add(f)
    db.commit()
    db.refresh(f)
    return f


def _mock_llm(contradicts: bool, reason: str = ""):
    m = MagicMock()
    m.is_available = True
    m.complete_json.return_value = {"contradicts": contradicts, "reason": reason}
    return m


class TestFreshness:
    def test_contradiction_flags_stale(self, db_session):
        from app.services.freshness_service import freshness_service

        skill = _approved_skill(db_session, "Pricing approval policy")
        _recent_fragment(db_session, "We now auto-approve discounts up to 30% without a manager.")

        with patch("app.services.freshness_service.llm_service", _mock_llm(True, "threshold changed")):
            freshness_service.scan(db_session)

        db_session.expire_all()
        refreshed = db_session.get(Skill, skill.id)
        assert refreshed.status == "stale"
        insights = db_session.exec(
            select(ActiveInsight).where(ActiveInsight.category == "freshness")
        ).all()
        assert any("Pricing approval policy" in i.observation for i in insights)
        audits = db_session.exec(select(AuditLog).where(AuditLog.action == "skill_stale")).all()
        assert any(a.target_id == str(skill.id) for a in audits)

    def test_no_contradiction_keeps_approved(self, db_session):
        from app.services.freshness_service import freshness_service

        skill = _approved_skill(db_session, "Stable refund policy")
        _recent_fragment(db_session, "Reminder: refunds still follow the usual flow.")

        with patch("app.services.freshness_service.llm_service", _mock_llm(False)):
            freshness_service.scan(db_session)

        db_session.expire_all()
        assert db_session.get(Skill, skill.id).status == "approved"

    def test_no_new_evidence_is_skipped(self, db_session):
        from app.services.freshness_service import freshness_service

        # Verified in the future → all existing evidence predates it, so this skill
        # is skipped and stays approved even though the contradiction verdict is True.
        skill = _approved_skill(db_session, "Future-verified policy", verified_days_ago=-5)

        with patch("app.services.freshness_service.llm_service", _mock_llm(True, "should not run")):
            freshness_service.scan(db_session)

        db_session.expire_all()
        assert db_session.get(Skill, skill.id).status == "approved"
