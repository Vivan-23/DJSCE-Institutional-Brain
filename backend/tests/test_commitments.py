"""Tests for the commitment (action item) API and service."""
from sqlmodel import select

from app.models.structured import Commitment, User
from app.services.employee_service import employee_service


def _register(client, email="commit@test.com"):
    res = client.post(
        "/api/v1/auth/register",
        json={"email": email, "full_name": "Commit User", "password": "pass1234"},
    )
    if res.status_code == 400:
        res = client.post("/api/v1/auth/login", json={"email": email, "password": "pass1234"})
    return res.json()["access_token"]


def _seed_commitment(db, description="Ship the thing", status="open", employee_id=None):
    c = Commitment(description=description, status=status, assignee_employee_id=employee_id)
    db.add(c)
    db.commit()
    db.refresh(c)
    return c


class TestCommitmentsAPI:
    def test_requires_auth(self, client):
        assert client.get("/api/v1/commitments").status_code == 401

    def test_list_commitments(self, client, db_session):
        _seed_commitment(db_session, "Build the API")
        token = _register(client)
        res = client.get("/api/v1/commitments", headers={"Authorization": f"Bearer {token}"})
        assert res.status_code == 200
        descriptions = [c["description"] for c in res.json()]
        assert "Build the API" in descriptions

    def test_patch_status(self, client, db_session):
        c = _seed_commitment(db_session, "Finish docs", status="open")
        token = _register(client)
        res = client.patch(
            f"/api/v1/commitments/{c.id}",
            json={"status": "done"},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert res.status_code == 200
        assert res.json()["status"] == "done"

    def test_patch_invalid_status_returns_400(self, client, db_session):
        c = _seed_commitment(db_session, "Whatever")
        token = _register(client)
        res = client.patch(
            f"/api/v1/commitments/{c.id}",
            json={"status": "banana"},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert res.status_code == 400

    def test_patch_nonexistent_returns_404(self, client):
        token = _register(client)
        import uuid
        res = client.patch(
            f"/api/v1/commitments/{uuid.uuid4()}",
            json={"status": "done"},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert res.status_code == 404

    def test_my_commitments(self, client, db_session):
        token = _register(client, email="mine@test.com")
        user = db_session.exec(select(User).where(User.email == "mine@test.com")).first()
        employee = employee_service.get_or_create_for_user(db_session, user)
        _seed_commitment(db_session, "My own task", employee_id=employee.id)
        res = client.get("/api/v1/commitments/mine", headers={"Authorization": f"Bearer {token}"})
        assert res.status_code == 200
        assert any(c["description"] == "My own task" for c in res.json())


class TestCommitmentService:
    def test_needs_followup_picks_stale_open_commitments(self, db_session):
        from datetime import datetime, timezone, timedelta
        from app.services.commitment_service import commitment_service

        old = _seed_commitment(db_session, "Old open task", status="open")
        # Backdate creation so it crosses the follow-up threshold
        old.created_at = datetime.now(timezone.utc) - timedelta(days=7)
        db_session.add(old)
        _seed_commitment(db_session, "Done task", status="done")
        db_session.commit()

        flagged = commitment_service.needs_followup(db_session)
        descriptions = [c.description for c in flagged]
        assert "Old open task" in descriptions
        assert "Done task" not in descriptions
