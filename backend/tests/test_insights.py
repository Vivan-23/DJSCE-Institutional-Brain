"""Tests for the insights endpoint — listing and dismissing."""
import pytest
from sqlmodel import Session
from app.models.structured import ActiveInsight
from tests.helpers import register


def _get_token(client) -> str:
    return register(client, "insights@test.com", "Insights User")


def _seed_insight(db_session: Session) -> ActiveInsight:
    insight = ActiveInsight(
        category="risk",
        observation="Test observation",
        impact_rationale="Test rationale",
        suggested_actions='["Action A", "Action B"]',
        confidence_score=0.9,
    )
    db_session.add(insight)
    db_session.commit()
    db_session.refresh(insight)
    return insight


class TestInsightsEndpoint:
    def test_get_insights_requires_auth(self, client):
        res = client.get("/api/v1/insights/")
        assert res.status_code == 401

    def test_get_insights_returns_list(self, client, db_session):
        token = _get_token(client)
        _seed_insight(db_session)
        res = client.get(
            "/api/v1/insights/",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert res.status_code == 200
        assert isinstance(res.json(), list)

    def test_dismiss_insight(self, client, db_session):
        token = _get_token(client)
        insight = _seed_insight(db_session)
        res = client.post(
            f"/api/v1/insights/{insight.id}/dismiss",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert res.status_code == 200
        assert res.json()["status"] == "dismissed"

    def test_dismiss_nonexistent_returns_404(self, client):
        token = _get_token(client)
        fake_id = "00000000-0000-0000-0000-000000000000"
        res = client.post(
            f"/api/v1/insights/{fake_id}/dismiss",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert res.status_code == 404
