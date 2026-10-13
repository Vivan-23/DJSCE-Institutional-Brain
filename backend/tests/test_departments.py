"""Per-department access: students and faculty retrieve their department + institution-wide material."""
import io
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

from app.models.structured import Meeting
from tests.helpers import register


def _h(token):
    return {"Authorization": f"Bearer {token}"}


class _FakeCollection:
    def __init__(self, documents, metadatas):
        self.result = {"documents": [documents], "metadatas": [metadatas]}

    def query(self, **kwargs):
        self.kwargs = kwargs
        return self.result


def _retrieve(collection, **kwargs):
    from app.services.rag_service import rag_service

    with (
        patch("app.core.chroma_db.chroma_conn") as conn,
        patch("app.services.embedding.embedding_service") as emb,
    ):
        conn.collection = collection
        emb.is_available = True
        emb.embed_texts.return_value = [[0.1]]
        return rag_service.retrieve("q", **kwargs)


class TestScope:
    def test_scope_by_role(self):
        from app.api.v1.auth import department_scope
        from app.models.structured import User

        def user(role, dept=None):
            return User(email="u", hashed_password="x", role=role, department=dept)

        assert department_scope(user("student", "CE")) == ["CE", "all"]
        assert department_scope(user("employee", "IT")) == ["IT", "all"]
        assert department_scope(user("student")) == ["all"]  # no department on record: fail closed
        assert department_scope(user("manager", "CE")) is None

    def test_retrieve_filters_department_in_query_and_rechecks(self):
        fake = _FakeCollection(
            ["CE fact", "IT fact", "college fact"],
            [
                {"visibility": "public", "department": "CE"},
                {"visibility": "public", "department": "IT"},
                {"visibility": "public", "department": "all"},
            ],
        )
        sources = _retrieve(fake, public_only=True, departments=["CE", "all"])
        assert fake.kwargs["where"] == {
            "$and": [{"visibility": "public"}, {"department": {"$in": ["CE", "all"]}}]
        }
        # The fake store ignored the filter; the re-check must still drop the IT hit.
        assert [s["excerpt"] for s in sources] == ["CE fact", "college fact"]

    def test_unrestricted_has_no_department_clause(self):
        fake = _FakeCollection(["x"], [{"visibility": "internal", "department": "IT"}])
        _retrieve(fake, public_only=False, departments=None)
        assert fake.kwargs["where"] is None

    def test_chat_passes_the_students_scope(self, client):
        token = register(client, "ce-student@test.com", role="student", department="CE")
        with patch("app.services.rag_service.rag_service.retrieve", return_value=[]) as retrieve:
            res = client.post(
                "/api/v1/chat", json={"messages": [{"role": "user", "content": "hi"}]}, headers=_h(token)
            )
        assert res.json()["departments"] == ["CE", "all"]
        assert retrieve.call_args.kwargs["departments"] == ["CE", "all"]


class TestMeetings:
    def _seed(self, db):
        now = datetime.now(timezone.utc)
        for title, dept in (("CE sync", "CE"), ("IT sync", "IT"), ("IQAC review", "all")):
            db.add(Meeting(title=title, occurred_at=now, department=dept))
        db.commit()

    def test_faculty_see_own_department_and_institution_wide(self, client, db_session):
        self._seed(db_session)
        token = register(client, "ce-faculty@test.com", role="employee", department="CE")
        titles = {m["title"] for m in client.get("/api/v1/transcripts", headers=_h(token)).json()}
        assert {"CE sync", "IQAC review"} <= titles and "IT sync" not in titles

    def test_other_departments_meeting_is_404(self, client, db_session):
        self._seed(db_session)
        manager = register(client, "coord@test.com", role="manager", department="CE")
        meetings = client.get("/api/v1/transcripts", headers=_h(manager)).json()
        assert {"CE sync", "IT sync", "IQAC review"} <= {m["title"] for m in meetings}  # coordinators see all
        it_id = next(m["id"] for m in meetings if m["title"] == "IT sync")
        faculty = register(client, "ce-faculty2@test.com", role="employee", department="CE")
        assert client.get(f"/api/v1/transcripts/{it_id}", headers=_h(faculty)).status_code == 404
        assert client.get(f"/api/v1/transcripts/{it_id}", headers=_h(manager)).status_code == 200


class TestIngestion:
    def test_document_department_is_forwarded(self, client):
        token = register(client, "uploader@test.com", role="employee")
        with patch("app.core.celery.process_document_task.delay") as task:
            task.return_value = MagicMock(id="t")
            res = client.post(
                "/api/v1/ingest/file",
                files={"file": ("ce.txt", io.BytesIO(b"CE lab rules"), "text/plain")},
                data={"visibility": "public", "department": "Computer Engineering"},
                headers=_h(token),
            )
        assert res.status_code == 202 and res.json()["department"] == "CE"
        assert task.call_args.args[3] == "CE"

    def test_unknown_department_is_rejected(self, client):
        token = register(client, "uploader2@test.com", role="employee")
        res = client.post(
            "/api/v1/ingest/file",
            files={"file": ("x.txt", io.BytesIO(b"text"), "text/plain")},
            data={"department": "Astrology"},
            headers=_h(token),
        )
        assert res.status_code == 400

    def test_fragment_department_reaches_vector_metadata(self, db_session):
        from app.services.fragment_service import fragment_service

        with (
            patch("app.core.chroma_db.chroma_conn") as conn,
            patch("app.services.embedding.embedding_service") as emb,
        ):
            emb.is_available = True
            emb.embed_texts.return_value = [[0.1]]
            frag = fragment_service.create_fragment(
                db_session, source_type="document", content="c", department="IT"
            )
        assert frag.department == "IT"
        assert conn.collection.add.call_args.kwargs["metadatas"][0]["department"] == "IT"


class TestRegistration:
    def test_register_resolves_department_name(self, client):
        res = client.post("/api/v1/auth/register", json={
            "email": "new-it@test.com", "full_name": "N", "password": "pass1234",
            "department": "Information Technology",
        })
        me = client.get("/api/v1/auth/me", headers=_h(res.json()["access_token"])).json()
        assert me["department"] == "IT" and me["role"] == "student"

    def test_register_rejects_unknown_department(self, client):
        res = client.post("/api/v1/auth/register", json={
            "email": "bad@test.com", "full_name": "N", "password": "pass1234", "department": "Nope",
        })
        assert res.status_code == 400
