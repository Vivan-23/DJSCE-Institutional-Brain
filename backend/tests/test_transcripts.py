"""Tests for transcript ingestion and the capture pipeline."""
from unittest.mock import patch, MagicMock

from sqlmodel import select

from app.models.structured import Meeting, Fragment, Commitment, Employee


def _get_token(client) -> str:
    res = client.post(
        "/api/v1/auth/register",
        json={"email": "trans@test.com", "full_name": "Trans User", "password": "pass1234"},
    )
    if res.status_code == 400:
        res = client.post(
            "/api/v1/auth/login",
            json={"email": "trans@test.com", "password": "pass1234"},
        )
    return res.json()["access_token"]


class TestTranscriptEndpoint:
    def test_post_transcript_queues(self, client):
        token = _get_token(client)
        with patch("app.core.celery.process_transcript_task.delay") as mock_task:
            mock_task.return_value = MagicMock(id="task-123")
            res = client.post(
                "/api/v1/transcripts",
                json={"title": "Sprint Planning", "transcript": "Alex: I'll do the API."},
                headers={"Authorization": f"Bearer {token}"},
            )
        assert res.status_code == 202
        assert res.json()["status"] == "queued"
        assert res.json()["task_id"] == "task-123"

    def test_post_empty_transcript_returns_400(self, client):
        token = _get_token(client)
        res = client.post(
            "/api/v1/transcripts",
            json={"title": "Empty", "transcript": "   "},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert res.status_code == 400

    def test_requires_auth(self, client):
        res = client.post(
            "/api/v1/transcripts",
            json={"title": "X", "transcript": "hello"},
        )
        assert res.status_code == 401


class TestTranscriptPipeline:
    """The full ingest pipeline with the LLM extraction mocked out."""

    def test_ingest_creates_meeting_fragments_and_commitments(self, db_session):
        from app.services.transcript_service import transcript_service
        from app.services.extraction_service import extraction_service

        fake_extraction = {
            "summary": "Team planned the refund flow.",
            "participants": ["Alex Chen", "Priya"],
            "decisions": ["Ship refund flow this week"],
            "commitments": [
                {"assignee": "Priya", "description": "Build the refund API", "due": None},
                {"assignee": "Alex Chen", "description": "Write the UI", "due": "2026-07-01"},
            ],
        }
        transcript = (
            "Alex Chen: We should ship the refund flow this week.\n"
            "Priya: I'll own the API changes.\n"
            "Alex Chen: I'll handle the UI.\n"
        )

        with patch.object(extraction_service, "extract_meeting", return_value=fake_extraction):
            result = transcript_service.ingest(
                db_session, transcript=transcript, title="Refund Planning"
            )

        from uuid import UUID
        meeting_id = UUID(result["meeting_id"])

        # Meeting persisted (scoped to this test's meeting — DB is shared across tests)
        meeting = db_session.get(Meeting, meeting_id)
        assert meeting is not None
        assert meeting.summary == "Team planned the refund flow."

        # Fragments created with speaker attribution
        fragments = db_session.exec(
            select(Fragment).where(Fragment.meeting_id == meeting_id)
        ).all()
        assert len(fragments) == 3
        assert all(f.source_type == "transcript" for f in fragments)

        # Commitments created and assignees resolved to employees
        commitments = db_session.exec(
            select(Commitment).where(Commitment.source_meeting_id == meeting_id)
        ).all()
        assert len(commitments) == 2
        assert {c.description for c in commitments} == {"Build the refund API", "Write the UI"}
        assert all(c.assignee_employee_id is not None for c in commitments)

        # Employees were created from the assignee names
        employees = {e.display_name for e in db_session.exec(select(Employee)).all()}
        assert "Priya" in employees
        assert "Alex Chen" in employees

        # Due date parsed where ISO-formatted
        ui = next(c for c in commitments if c.description == "Write the UI")
        assert ui.due_date is not None and ui.due_date.year == 2026

        assert result["commitments_created"] == 2
        assert result["fragments"] == 3
