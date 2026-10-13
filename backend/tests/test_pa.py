"""Tests for the Company PA: follow-ups and the end-of-day check-in."""
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch

from sqlmodel import select

from app.models.structured import CheckIn, Commitment, CommitmentUpdate, Fragment, User
from app.services.employee_service import employee_service
from tests.helpers import register


def _register(client, email="pa@test.com"):
    return register(client, email, "PA User")


def _employee_for(db, email):
    user = db.exec(select(User).where(User.email == email)).first()
    return employee_service.get_or_create_for_user(db, user)


def _stale_commitment(db, employee_id, description="Ship the auth feature"):
    c = Commitment(description=description, status="open", assignee_employee_id=employee_id)
    db.add(c)
    db.commit()
    db.refresh(c)
    c.created_at = datetime.now(timezone.utc) - timedelta(days=7)
    db.add(c)
    db.commit()
    db.refresh(c)
    return c


class TestFollowups:
    def test_requires_auth(self, client):
        assert client.get("/api/v1/pa/followups").status_code == 401

    def test_lists_stale_commitment_as_followup(self, client, db_session):
        email = "followup@test.com"
        token = _register(client, email)
        emp = _employee_for(db_session, email)
        _stale_commitment(db_session, emp.id, "Ship the auth feature")

        unavailable = MagicMock()
        unavailable.is_available = False
        with patch("app.services.pa_service.llm_service", unavailable):
            res = client.get("/api/v1/pa/followups", headers={"Authorization": f"Bearer {token}"})
        assert res.status_code == 200
        items = res.json()
        match = [f for f in items if f["description"] == "Ship the auth feature"]
        assert match and "auth feature" in match[0]["message"]

    def test_reply_records_update_and_fragment(self, client, db_session):
        email = "reply@test.com"
        token = _register(client, email)
        emp = _employee_for(db_session, email)
        c = _stale_commitment(db_session, emp.id, "Finish the migration")

        unavailable = MagicMock()
        unavailable.is_available = False
        with patch("app.services.pa_service.llm_service", unavailable):
            res = client.post(
                f"/api/v1/pa/followups/{c.id}/reply",
                json={"text": "Done — merged this morning."},
                headers={"Authorization": f"Bearer {token}"},
            )
        assert res.status_code == 200

        updates = db_session.exec(
            select(CommitmentUpdate).where(CommitmentUpdate.commitment_id == c.id)
        ).all()
        assert any(u.source == "followup" for u in updates)
        frags = db_session.exec(select(Fragment).where(Fragment.source_type == "followup")).all()
        assert any(f.author_employee_id == emp.id for f in frags)


class TestCheckin:
    def test_checkin_creates_with_opener(self, client, db_session):
        token = _register(client, "ci-open@test.com")
        res = client.get("/api/v1/pa/checkin", headers={"Authorization": f"Bearer {token}"})
        assert res.status_code == 200
        body = res.json()
        assert body["completed"] is False
        assert body["conversation"][0]["role"] == "assistant"

    def test_message_applies_structured_updates(self, client, db_session):
        email = "ci-msg@test.com"
        token = _register(client, email)
        emp = _employee_for(db_session, email)
        c = Commitment(description="Build the dashboard", status="open", assignee_employee_id=emp.id)
        db_session.add(c)
        db_session.commit()
        db_session.refresh(c)

        mock_llm = MagicMock()
        mock_llm.is_available = True
        mock_llm.complete_json.return_value = {
            "reply": "Awesome, nice progress!",
            "updates": [
                {"commitment_id": str(c.id), "status": "done", "summary": "dashboard shipped"}
            ],
            "new_commitments": [{"description": "Write the dashboard docs"}],
        }
        with patch("app.services.pa_service.llm_service", mock_llm):
            res = client.post(
                "/api/v1/pa/checkin/message",
                json={"text": "I finished the dashboard and will write docs next."},
                headers={"Authorization": f"Bearer {token}"},
            )
        assert res.status_code == 200
        assert res.json()["reply"] == "Awesome, nice progress!"

        db_session.expire_all()
        refreshed = db_session.get(Commitment, c.id)
        assert refreshed.status == "done"
        descriptions = {
            x.description for x in db_session.exec(
                select(Commitment).where(Commitment.assignee_employee_id == emp.id)
            )
        }
        assert "Write the dashboard docs" in descriptions

    def test_complete_marks_checkin_done(self, client, db_session):
        token = _register(client, "ci-done@test.com")
        res = client.post("/api/v1/pa/checkin/complete", headers={"Authorization": f"Bearer {token}"})
        assert res.status_code == 200
        assert res.json()["completed"] is True
