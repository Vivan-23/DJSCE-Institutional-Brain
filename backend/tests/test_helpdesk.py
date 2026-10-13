"""Help Desk: ticket creation, triage, privacy of AI drafts, staff replies."""
from unittest.mock import MagicMock, patch

from app.services.ticket_service import ticket_service
from tests.helpers import register


def _h(token):
    return {"Authorization": f"Bearer {token}"}


def _no_llm():
    """Force the keyword fallback by making the triage LLM unavailable."""
    mock = MagicMock()
    mock.is_available = False
    return patch("app.services.ticket_service.llm_service", mock)


def _create(client, token, subject, description):
    with _no_llm():
        return client.post(
            "/api/v1/helpdesk/tickets",
            json={"subject": subject, "description": description},
            headers=_h(token),
        )


class TestKeywordTriage:
    def test_routes_exam_questions_to_exam_cell(self):
        t = ticket_service.keyword_triage("How do I apply for revaluation of my exam marks?")
        assert t["category"] == "examinations"
        assert t["method"] == "keyword"

    def test_unknown_text_is_general(self):
        assert ticket_service.keyword_triage("Hello there")["category"] == "general"

    def test_urgent_words_raise_priority(self):
        assert ticket_service.keyword_triage("URGENT: cannot access the lab portal")["priority"] == "high"


class TestLLMTriage:
    def test_rejects_invented_category_and_falls_back(self):
        mock = MagicMock()
        mock.is_available = True
        mock.complete_json.return_value = {"category": "hostel-mess", "priority": "high"}
        with patch("app.services.ticket_service.llm_service", mock):
            t = ticket_service.triage("Which electives are offered in semester VI?")
        assert t["method"] == "keyword"
        assert t["category"] == "academics"

    def test_accepts_valid_llm_triage(self):
        mock = MagicMock()
        mock.is_available = True
        mock.complete_json.return_value = {"category": "careers", "priority": "LOW", "rationale": "Placement query"}
        with patch("app.services.ticket_service.llm_service", mock):
            t = ticket_service.triage("Which companies visit for placements?")
        assert t == {"category": "careers", "priority": "low", "method": "llm", "rationale": "Placement query"}


class TestTicketFlow:
    def test_student_creates_ticket_and_never_sees_ai_draft(self, client):
        token = register(client, "hd-student@test.com", role="student")
        res = _create(client, token, "Re-evaluation", "How do I apply for exam re-evaluation?")
        assert res.status_code == 201
        body = res.json()
        assert body["category"] == "examinations"
        assert body["routed_to"] == "Examination Cell"
        assert body["status"] == "open"
        assert "ai_draft_reply" not in body and "ai_sources" not in body

        detail = client.get(f"/api/v1/helpdesk/tickets/{body['id']}", headers=_h(token)).json()
        assert "ai_draft_reply" not in detail
        mine = client.get("/api/v1/helpdesk/tickets/mine", headers=_h(token)).json()
        assert body["id"] in [t["id"] for t in mine]

    def test_staff_sees_draft_with_sources_and_replies(self, client):
        student = register(client, "hd-student2@test.com", role="student")
        tid = _create(client, student, "Lab access", "The lab workstation login is not working").json()["id"]

        staff = register(client, "hd-faculty@test.com", role="employee")
        queued = client.get("/api/v1/helpdesk/tickets?status=open", headers=_h(staff)).json()
        ticket = next(t for t in queued if t["id"] == tid)
        assert ticket["ai_draft_reply"] == "Mock answer from LLM [1]"
        assert ticket["ai_sources"][0]["excerpt"] == "mock context chunk"
        assert ticket["raised_by_role"] == "student"

        res = client.post(
            f"/api/v1/helpdesk/tickets/{tid}/reply",
            json={"reply": "Please reset your password at the lab desk.", "close": False},
            headers=_h(staff),
        )
        assert res.status_code == 200
        seen = client.get(f"/api/v1/helpdesk/tickets/{tid}", headers=_h(student)).json()
        assert seen["status"] == "answered"
        assert seen["reply"] == "Please reset your password at the lab desk."

    def test_students_cannot_see_each_others_tickets(self, client):
        owner = register(client, "hd-owner@test.com", role="student")
        other = register(client, "hd-other@test.com", role="student")
        tid = _create(client, owner, "Attendance", "Am I below the attendance requirement?").json()["id"]
        assert client.get(f"/api/v1/helpdesk/tickets/{tid}", headers=_h(other)).status_code == 404

    def test_student_cannot_reply_or_reopen(self, client):
        token = register(client, "hd-student3@test.com", role="student")
        tid = _create(client, token, "Placements", "Which companies recruit?").json()["id"]
        assert client.post(
            f"/api/v1/helpdesk/tickets/{tid}/reply", json={"reply": "self-answer"}, headers=_h(token)
        ).status_code == 403
        assert client.patch(
            f"/api/v1/helpdesk/tickets/{tid}", json={"status": "answered"}, headers=_h(token)
        ).status_code == 403
        closed = client.patch(f"/api/v1/helpdesk/tickets/{tid}", json={"status": "closed"}, headers=_h(token))
        assert closed.status_code == 200 and closed.json()["status"] == "closed"

    def test_categories_include_quick_questions(self, client):
        token = register(client, "hd-cats@test.com", role="student")
        cats = client.get("/api/v1/helpdesk/categories", headers=_h(token)).json()
        assert any(c["key"] == "examinations" and c["quick_questions"] for c in cats)
