"""Academic calendar + deadline reminders."""
from datetime import date, datetime, timezone
from unittest.mock import patch
from uuid import uuid4

from sqlmodel import select

from app.core.institution_config import CalendarEvent, InstitutionConfig
from app.models.structured import ActiveInsight, Commitment, Employee, User
from tests.helpers import register

TODAY = date(2026, 10, 20)

_EVENTS = [
    CalendarEvent(start=date(2026, 10, 1), title="Past event"),
    CalendarEvent(start=date(2026, 10, 19), end=date(2026, 10, 23), title="Exam week", kind="exam"),
    CalendarEvent(start=date(2026, 10, 22), title="Marks entry closes", kind="deadline", audience="staff"),
    CalendarEvent(start=date(2026, 10, 26), title="CE elective registration", kind="deadline",
                  audience="students", department="CE"),
    CalendarEvent(start=date(2026, 10, 27), title="IT lab review", audience="students", department="IT"),
    CalendarEvent(start=date(2027, 3, 1), title="Far future"),
]


def _cfg():
    return patch(
        "app.services.calendar_service.get_institution_config",
        return_value=InstitutionConfig(calendar=list(_EVENTS)),
    )


def _titles(items):
    return [i["title"] for i in items]


class TestEvents:
    def test_student_sees_own_department_and_student_events(self):
        from app.services.calendar_service import calendar_service

        with _cfg():
            items = calendar_service.events_for(staff=False, departments=["CE", "all"], today=TODAY, days=60)
        assert _titles(items) == ["Exam week", "CE elective registration"]
        exam = items[0]
        assert exam["days_left"] == 0 and exam["urgency"] == "today"  # started, not over
        assert items[1]["days_left"] == 6 and items[1]["urgency"] == "upcoming"

    def test_staff_events_and_soon_urgency(self):
        from app.services.calendar_service import calendar_service

        with _cfg():
            items = calendar_service.events_for(staff=True, departments=None, today=TODAY, days=60)
        assert _titles(items) == ["Exam week", "Marks entry closes"]
        assert items[1]["urgency"] == "soon"

    def test_config_parses_calendar_block(self, tmp_path):
        from app.core import institution_config as ic

        path = tmp_path / "inst.yaml"
        path.write_text(
            "academic_calendar:\n"
            "  note: demo\n"
            "  events:\n"
            "    - { date: '2026-11-02', end: '2026-11-06', title: 'Vacation', kind: holiday }\n"
            "    - { date: 'not-a-date', title: 'Bad' }\n"
            "    - { date: '2026-10-01', title: 'Staff only', audience: staff }\n",
            encoding="utf-8",
        )
        ic.get_institution_config.cache_clear()
        try:
            with patch.dict("os.environ", {"INSTITUTION_CONFIG": str(path)}):
                cfg = ic.get_institution_config()
        finally:
            ic.get_institution_config.cache_clear()
        assert [e.title for e in cfg.calendar] == ["Staff only", "Vacation"]  # sorted, bad date skipped
        assert cfg.calendar[1].end == date(2026, 11, 6) and cfg.calendar_note == "demo"


class TestCommitmentsAndReminders:
    def _staff_with_commitments(self, db):
        tag = uuid4().hex[:6]  # the test DB is shared, so keep rows distinguishable
        user = User(email=f"cal-staff-{tag}@test.com", hashed_password="x", role="employee")
        db.add(user)
        db.commit()
        emp = Employee(display_name="Cal Staff", user_id=user.id)
        db.add(emp)
        db.commit()
        for desc, due, status in (
            ("Submit CO-PO matrix", datetime(2026, 10, 18, tzinfo=timezone.utc), "open"),  # overdue
            ("Finish lab audit", datetime(2026, 10, 22, tzinfo=timezone.utc), "in_progress"),
            ("Already done", datetime(2026, 10, 21, tzinfo=timezone.utc), "done"),
            ("No due date", None, "open"),
        ):
            db.add(Commitment(assignee_employee_id=emp.id, description=desc, due_date=due, status=status))
        db.commit()
        return user, tag

    def test_staff_upcoming_merges_commitments(self, db_session):
        from app.services.calendar_service import calendar_service

        user, _ = self._staff_with_commitments(db_session)
        with _cfg():
            items = calendar_service.upcoming(db_session, user, staff=True, departments=None, days=60, today=TODAY)
        commitments = [i for i in items if i["source"] == "commitment"]
        assert _titles(commitments) == ["Submit CO-PO matrix", "Finish lab audit"]
        assert commitments[0]["urgency"] == "overdue"

    def test_reminders_are_posted_once(self, db_session):
        from app.services.calendar_service import calendar_service

        self._staff_with_commitments(db_session)
        with _cfg():
            first = calendar_service.post_reminders(db_session, today=TODAY)
            second = calendar_service.post_reminders(db_session, today=TODAY)
        assert first >= 4  # exam week, marks entry, overdue + soon commitment (+ other tests' rows)
        assert second == 0  # idempotent
        rows = db_session.exec(select(ActiveInsight).where(ActiveInsight.category == "deadline")).all()
        assert any("Submit CO-PO matrix" in r.observation and "overdue" in r.observation for r in rows)


class TestEndpoint:
    def test_student_calendar_has_no_commitments(self, client):
        token = register(client, "cal-student@test.com", role="student", department="IT")
        with _cfg():
            res = client.get("/api/v1/calendar?days=366", headers={"Authorization": f"Bearer {token}"})
        assert res.status_code == 200
        body = res.json()
        assert all(i["source"] == "calendar" for i in body["items"])
        assert "CE elective registration" not in _titles(body["items"])
        assert body["soon_days"] == 3

    def test_requires_login(self, client):
        assert client.get("/api/v1/calendar").status_code == 401
