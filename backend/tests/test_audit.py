"""Tests for the audit trail API and RBAC."""
from sqlmodel import select

from app.models.structured import User
from app.services.audit_service import audit_service
from tests.helpers import register


def _register(client, email):
    return register(client, email, "Audit User")


def _make_manager(db, email):
    user = db.exec(select(User).where(User.email == email)).first()
    user.role = "manager"
    db.add(user)
    db.commit()


class TestAudit:
    def test_requires_manager(self, client):
        token = _register(client, "audit-emp@test.com")
        res = client.get("/api/v1/audit", headers={"Authorization": f"Bearer {token}"})
        assert res.status_code == 403

    def test_lists_entries(self, client, db_session):
        email = "audit-mgr@test.com"
        token = _register(client, email)
        _make_manager(db_session, email)
        audit_service.record(
            db_session, actor="tester", action="unit_test_action", target_id="abc",
            metadata={"k": "v"},
        )
        res = client.get(
            "/api/v1/audit?action=unit_test_action",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert res.status_code == 200
        entries = res.json()
        assert entries and entries[0]["action"] == "unit_test_action"
        assert entries[0]["metadata"] == {"k": "v"}
