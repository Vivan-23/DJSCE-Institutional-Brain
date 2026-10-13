"""Coordinator analytics + the chat question log behind it."""
from datetime import datetime, timedelta, timezone
from uuid import uuid4

from sqlmodel import select

from app.models.structured import Commitment, Meeting, QueryLog, Ticket, User
from tests.helpers import register

NOW = datetime(2026, 10, 20, 12, tzinfo=timezone.utc)


def _h(token):
    return {"Authorization": f"Bearer {token}"}


class TestQueryLog:
    def test_chat_logs_question_without_user_id(self, client, db_session):
        token = register(client, "qlog-student@test.com", role="student", department="CE")
        client.post("/api/v1/chat", json={"messages": [{"role": "user", "content": "What is the attendance rule?"}]},
                    headers=_h(token))
        row = db_session.exec(select(QueryLog).where(QueryLog.question == "What is the attendance rule?")).first()
        assert row is not None and row.role == "student" and row.department == "CE"
        assert not hasattr(row, "user_id")


class TestSummary:
    def _seed(self, db):
        tag = uuid4().hex[:6]
        user = User(email=f"an-{tag}@test.com", hashed_password="x", role="student")
        db.add(user)
        m = Meeting(title=f"IQAC review {tag}", occurred_at=NOW, department="all")
        db.add(m)
        db.commit()
        for status, due in (("open", NOW - timedelta(days=2)), ("in_progress", NOW + timedelta(days=5)), ("done", None)):
            db.add(Commitment(description=f"c-{status}", status=status, due_date=due, source_meeting_id=m.id))
        db.add(Ticket(raised_by_user_id=user.id, subject="s1", description="d", status="answered", category="examinations",
                      created_at=NOW - timedelta(hours=10), replied_at=NOW - timedelta(hours=4)))
        db.add(Ticket(raised_by_user_id=user.id, subject="s2", description="d", status="open", category="facilities",
                      created_at=NOW - timedelta(hours=72)))
        for q, n in ((f"Exam revaluation deadline {tag}?", 0), (f"exam revaluation deadline {tag}", 2),
                     (f"Hostel curfew {tag}", 0)):
            db.add(QueryLog(question=q, role="student", source_count=n, created_at=NOW - timedelta(days=1)))
        db.add(QueryLog(question=f"old {tag}", role="student", source_count=1, created_at=NOW - timedelta(days=90)))
        db.commit()
        return tag

    def test_summary_numbers(self, db_session):
        from app.services.analytics_service import analytics_service

        tag = self._seed(db_session)
        s = analytics_service.summary(db_session, days=30, now=NOW)

        row = next(r for r in s["commitments_by_meeting"] if r["meeting"] == f"IQAC review {tag}")
        assert (row["open"], row["done"], row["overdue"], row["total"]) == (2, 1, 1, 3)

        t = s["tickets"]
        assert t["resolution_hours"]["n"] >= 1 and t["open_over_48h"] >= 1

        q = s["questions"]
        top = next(g for g in q["top"] if tag in g["question"].lower() and "revaluation" in g["question"].lower())
        assert top["count"] == 2 and top["no_sources"] == 1  # two phrasings grouped; one found nothing
        assert any(f"Hostel curfew {tag}" == g["question"] for g in q["knowledge_gaps"])
        assert not any(f"old {tag}" == g["question"] for g in q["top"])  # outside the window
        assert "examinations" in q["by_topic"]


class TestEndpoint:
    def test_coordinator_only(self, client):
        for role, code in (("student", 403), ("employee", 403), ("manager", 200), ("admin", 200)):
            token = register(client, f"an-{role}@test.com", role=role)
            assert client.get("/api/v1/analytics", headers=_h(token)).status_code == code

    def test_shape(self, client):
        token = register(client, "an-coord@test.com", role="manager")
        body = client.get("/api/v1/analytics?days=7", headers=_h(token)).json()
        assert set(body) >= {"commitments_by_meeting", "tickets", "questions", "knowledge"}
        assert body["questions"]["days"] == 7
