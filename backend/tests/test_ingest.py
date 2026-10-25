"""Tests for the document ingest endpoint."""
import io
import pytest
from unittest.mock import patch, MagicMock

from tests.helpers import register


def _get_token(client) -> str:
    return register(client, "ingest@test.com", "Ingest User")


class TestIngestEndpoint:
    def test_upload_txt_file_returns_202(self, client):
        token = _get_token(client)
        with patch("app.core.celery.process_document_task.delay") as mock_task:
            mock_task.return_value = MagicMock(id="fake-task-id")
            res = client.post(
                "/api/v1/ingest/file",
                files={"file": ("notes.txt", b"Meeting notes content here.", "text/plain")},
                headers={"Authorization": f"Bearer {token}"},
            )
        assert res.status_code == 202
        data = res.json()
        assert data["status"] == "queued"
        assert data["filename"] == "notes.txt"

    def test_upload_without_auth_returns_401(self, client):
        res = client.post(
            "/api/v1/ingest/file",
            files={"file": ("notes.txt", b"content", "text/plain")},
        )
        assert res.status_code == 401

    def test_unsupported_extension_returns_400(self, client):
        token = _get_token(client)
        res = client.post(
            "/api/v1/ingest/file",
            files={"file": ("malware.exe", b"\x00\x01\x02", "application/octet-stream")},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert res.status_code == 400

    def test_empty_text_file_returns_400(self, client):
        token = _get_token(client)
        with patch("app.core.celery.process_document_task.delay"):
            res = client.post(
                "/api/v1/ingest/file",
                files={"file": ("empty.txt", b"   \n\t  ", "text/plain")},
                headers={"Authorization": f"Bearer {token}"},
            )
        assert res.status_code == 400

    def test_oversized_file_returns_413(self, client):
        token = _get_token(client)
        big_content = b"a" * (11 * 1024 * 1024)  # 11 MB
        res = client.post(
            "/api/v1/ingest/file",
            files={"file": ("huge.txt", big_content, "text/plain")},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert res.status_code == 413


class TestDocumentVisibility:
    def test_visibility_is_forwarded_to_the_task(self, client):
        token = _get_token(client)
        with patch("app.core.celery.process_document_task.delay") as mock_task:
            mock_task.return_value = MagicMock(id="t")
            res = client.post(
                "/api/v1/ingest/file",
                files={"file": ("faq.txt", io.BytesIO(b"Public FAQ"), "text/plain")},
                data={"visibility": "public"},
                headers={"Authorization": f"Bearer {token}"},
            )
        assert res.status_code == 202
        assert res.json()["visibility"] == "public"
        assert mock_task.call_args.args == ("Public FAQ", "faq.txt", "public", "all")

    def test_rejects_unknown_visibility(self, client):
        token = _get_token(client)
        res = client.post(
            "/api/v1/ingest/file",
            files={"file": ("x.txt", io.BytesIO(b"text"), "text/plain")},
            data={"visibility": "everyone"},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert res.status_code == 400


class TestDocumentTask:
    def test_document_chunks_become_fragments_with_visibility(self, test_engine):
        from sqlmodel import Session, select

        from app.core.celery import process_document_task
        from app.models.structured import Fragment

        ner = MagicMock()
        ner.extract_entities.return_value = {"persons": [], "orgs": []}
        with (
            patch("app.core.db.engine", test_engine),
            patch("app.services.ner_service.ner_service", ner),
            patch("app.services.fragment_service.embedding_mod.embedding_service") as emb,
        ):
            emb.is_available = False  # skip vector indexing; we assert on Postgres rows
            result = process_document_task("Attendance must be at least 75 percent.", "policy-kb.txt", "public")

        assert result["chunks_stored"] >= 1
        with Session(test_engine) as db:
            frags = db.exec(select(Fragment).where(Fragment.source_ref == "policy-kb.txt")).all()
        assert frags and all(f.source_type == "document" and f.visibility == "public" for f in frags)

    def test_web_content_keeps_its_source_url(self, test_engine):
        from sqlmodel import Session, select

        from app.core.celery import process_document_task
        from app.models.structured import Fragment

        text = (
            "[PUBLIC DJSCE INFORMATION · Source: https://www.djsce.ac.in/about · Retrieved: 2026-10-13]\n"
            "Institution overview\n\n"
            "Q: Who runs the college?\nA: SVKM. (Source: https://www.djsce.ac.in/svkm)\n\n"
            + "Filler paragraph about the campus. " * 40
        )
        ner = MagicMock()
        ner.extract_entities.return_value = {"persons": [], "orgs": []}
        with (
            patch("app.core.db.engine", test_engine),
            patch("app.services.ner_service.ner_service", ner),
            patch("app.services.fragment_service.embedding_mod.embedding_service") as emb,
        ):
            emb.is_available = False
            process_document_task(text, "kb_overview.txt", "public", "all")
        with Session(test_engine) as db:
            urls = [f.source_url for f in db.exec(select(Fragment).where(Fragment.source_ref == "kb_overview.txt"))]
        assert "https://www.djsce.ac.in/svkm" in urls  # the Q&A's own citation wins
        assert all(u and u.startswith("https://www.djsce.ac.in/") for u in urls)  # others fall back to the header


class TestSourceUrls:
    def test_no_source_means_none(self):
        from app.services.parser import source_urls

        assert source_urls("Internal SOP text", ["Internal SOP text"]) == [None]


class TestDocumentList:
    def _seed(self):
        from sqlmodel import Session
        from app.models.structured import Fragment
        from tests.helpers import _engine
        with Session(_engine) as db:
            for ref, dept, n in (("ce-syllabus.pdf", "CE", 2), ("it-rules.pdf", "IT", 1), ("calendar.pdf", "all", 1)):
                for i in range(n):
                    db.add(Fragment(content=f"{ref} part {i}", source_type="document", source_ref=ref, department=dept))
            db.add(Fragment(content="said in a meeting", source_type="transcript", source_ref="m1", department="CE"))
            db.commit()

    def test_faculty_see_own_department_and_institution_wide(self, client):
        self._seed()
        token = register(client, "fac.docs@test.com", role="employee", department="CE")
        res = client.get("/api/v1/ingest/documents", headers={"Authorization": f"Bearer {token}"})
        assert res.status_code == 200
        docs = {d["filename"]: d for d in res.json()}
        assert {"ce-syllabus.pdf", "calendar.pdf"} <= set(docs)
        assert "it-rules.pdf" not in docs and "m1" not in docs  # not IT's, not transcripts
        assert all(d["department"] in ("CE", "all") for d in docs.values())
        assert docs["ce-syllabus.pdf"]["passages"] >= 2

    def test_coordinator_sees_every_department(self, client):
        self._seed()
        token = register(client, "coord.docs@test.com", role="manager")
        res = client.get("/api/v1/ingest/documents", headers={"Authorization": f"Bearer {token}"})
        assert {"ce-syllabus.pdf", "it-rules.pdf", "calendar.pdf"} <= {d["filename"] for d in res.json()}

    def test_students_cannot_list(self, client):
        token = register(client, "stud.docs@test.com", role="student")
        res = client.get("/api/v1/ingest/documents", headers={"Authorization": f"Bearer {token}"})
        assert res.status_code == 403
