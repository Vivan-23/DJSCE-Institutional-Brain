"""Tests for source connectors (FR1) and connector RBAC."""
from sqlmodel import select

from app.models.structured import Fragment, User
from tests.helpers import register


def _register(client, email):
    return register(client, email, "Src User")


def _make_manager(db, email):
    user = db.exec(select(User).where(User.email == email)).first()
    user.role = "manager"
    db.add(user)
    db.commit()


class TestSources:
    def test_list_sources(self, client):
        token = _register(client, "src-list@test.com")
        res = client.get("/api/v1/sources", headers={"Authorization": f"Bearer {token}"})
        assert res.status_code == 200
        names = {s["name"] for s in res.json()}
        assert {"manual", "slack", "db"} <= names
        manual = next(s for s in res.json() if s["name"] == "manual")
        assert manual["configured"] is True

    def test_sync_requires_manager(self, client):
        token = _register(client, "src-emp@test.com")
        res = client.post(
            "/api/v1/sources/manual/sync",
            json={"items": [{"content": "hello"}]},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert res.status_code == 403

    def test_unknown_connector_404(self, client, db_session):
        email = "src-404@test.com"
        token = _register(client, email)
        _make_manager(db_session, email)
        res = client.post(
            "/api/v1/sources/nope/sync",
            json={"items": []},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert res.status_code == 404

    def test_manual_sync_stores_fragments(self, client, db_session):
        email = "src-sync@test.com"
        token = _register(client, email)
        _make_manager(db_session, email)
        res = client.post(
            "/api/v1/sources/manual/sync",
            json={
                "items": [
                    {"content": "Escalations go to the on-call lead.", "author": "Dana"},
                    {"content": "We close tickets after 3 days of no reply."},
                ]
            },
            headers={"Authorization": f"Bearer {token}"},
        )
        assert res.status_code == 200
        assert res.json()["fragments_stored"] == 2
        stored = db_session.exec(
            select(Fragment).where(Fragment.source_type == "manual")
        ).all()
        assert len(stored) >= 2
