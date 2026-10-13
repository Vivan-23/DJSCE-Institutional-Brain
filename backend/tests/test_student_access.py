"""Student role: least-privilege registration, staff-only data, public-only retrieval."""
from unittest.mock import patch

import pytest

from tests.helpers import register

STAFF_ONLY_GETS = [
    "/api/v1/transcripts",
    "/api/v1/commitments",
    "/api/v1/commitments/mine",
    "/api/v1/skills",
    "/api/v1/insights",
    "/api/v1/graph/data",
    "/api/v1/graph/stats",
    "/api/v1/pa/followups",
    "/api/v1/pa/checkin",
    "/api/v1/sources",
    "/api/v1/audit",
    "/api/v1/helpdesk/tickets",
]


def _h(token):
    return {"Authorization": f"Bearer {token}"}


class TestRegistration:
    def test_self_registration_creates_a_student(self, client):
        res = client.post(
            "/api/v1/auth/register",
            json={"email": "fresh-student@test.com", "full_name": "Fresh", "password": "pass1234"},
        )
        token = res.json()["access_token"]
        me = client.get("/api/v1/auth/me", headers=_h(token)).json()
        assert me["role"] == "student"


class TestStaffOnlyEndpoints:
    @pytest.mark.parametrize("path", STAFF_ONLY_GETS)
    def test_student_is_forbidden(self, client, path):
        token = register(client, "blocked-student@test.com", role="student")
        assert client.get(path, headers=_h(token)).status_code == 403

    def test_student_cannot_upload_documents(self, client):
        token = register(client, "upload-student@test.com", role="student")
        res = client.post(
            "/api/v1/ingest/file",
            files={"file": ("x.txt", b"hello", "text/plain")},
            headers=_h(token),
        )
        assert res.status_code == 403

    def test_faculty_can_read_meetings(self, client):
        token = register(client, "faculty-reader@test.com", role="employee")
        assert client.get("/api/v1/transcripts", headers=_h(token)).status_code == 200


class TestPublicOnlyRetrieval:
    def test_student_chat_filters_to_public_evidence(self, client):
        token = register(client, "chat-student@test.com", role="student")
        with patch("app.services.rag_service.rag_service.retrieve", return_value=[]) as retrieve:
            res = client.post(
                "/api/v1/chat",
                json={"messages": [{"role": "user", "content": "What is the attendance rule?"}]},
                headers=_h(token),
            )
        assert res.status_code == 200
        assert res.json()["scope"] == "public"
        assert retrieve.call_args.kwargs["public_only"] is True

    def test_staff_chat_searches_everything(self, client):
        token = register(client, "chat-faculty@test.com", role="employee")
        with patch("app.services.rag_service.rag_service.retrieve", return_value=[]) as retrieve:
            res = client.post(
                "/api/v1/chat",
                json={"messages": [{"role": "user", "content": "What did the council decide?"}]},
                headers=_h(token),
            )
        assert res.json()["scope"] == "all"
        assert retrieve.call_args.kwargs["public_only"] is False

    def test_retrieve_passes_visibility_filter_and_drops_internal_hits(self):
        from app.services.rag_service import rag_service

        class FakeCollection:
            def query(self, **kwargs):
                self.kwargs = kwargs
                # A misbehaving store that ignores the filter must still not leak.
                return {
                    "documents": [["public fact", "internal minutes"]],
                    "metadatas": [[{"visibility": "public", "source_ref": "faq.txt"}, {"visibility": "internal"}]],
                }

        fake = FakeCollection()
        with (
            patch("app.core.chroma_db.chroma_conn") as conn,
            patch("app.services.embedding.embedding_service") as emb,
        ):
            conn.collection = fake
            emb.is_available = True
            emb.embed_texts.return_value = [[0.1]]
            sources = rag_service.retrieve("q", public_only=True)

        assert fake.kwargs["where"] == {"visibility": "public"}
        assert [s["excerpt"] for s in sources] == ["public fact"]
        assert sources[0]["source_ref"] == "faq.txt"

    def test_chat_returns_sources(self, client):
        token = register(client, "chat-sources@test.com", role="employee")
        res = client.post(
            "/api/v1/chat",
            json={"messages": [{"role": "user", "content": "anything"}]},
            headers=_h(token),
        )
        body = res.json()
        assert body["response"] == "Mock answer from LLM [1]"
        assert body["sources"][0]["excerpt"] == "mock context chunk"
