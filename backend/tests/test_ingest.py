"""Tests for the document ingest endpoint."""
import io
import pytest
from unittest.mock import patch, MagicMock


def _get_token(client) -> str:
    """Helper: register a user and return a valid JWT."""
    res = client.post(
        "/api/v1/auth/register",
        json={"email": "ingest@test.com", "full_name": "Ingest User", "password": "pass1234"},
    )
    # Idempotent — if email already exists, log in instead
    if res.status_code == 400:
        res = client.post(
            "/api/v1/auth/login",
            json={"email": "ingest@test.com", "password": "pass1234"},
        )
    return res.json()["access_token"]


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
