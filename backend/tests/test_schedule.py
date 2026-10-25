"""Teaching schedule: recurring entries expand per date; exceptions change only their date."""
from datetime import date, timedelta

from sqlmodel import select

from app.models.structured import TimetableEntry, TimetableImport, User
from tests.helpers import register


def _h(token):
    return {"Authorization": f"Bearer {token}"}


def _monday(offset_weeks: int = 1) -> date:
    today = date.today()
    return today - timedelta(days=today.weekday()) + timedelta(weeks=offset_weeks)


def _publish(db, user_email: str, *, status: str = "published", weekday: int = 0) -> TimetableEntry:
    user = db.exec(select(User).where(User.email == user_email)).first()
    imp = TimetableImport(class_key="TY-C2", year_label="TY", division="C2", source_filename="ty_c2.docx",
                          source_sha256="x" * 64, status=status)
    db.add(imp)
    db.commit()
    entry = TimetableEntry(import_id=imp.id, weekday=weekday, start_time="09:00", end_time="10:00",
                           subject="DBMS", room="501", faculty_abbrev="KD", faculty_user_id=user.id)
    db.add(entry)
    db.commit()
    db.refresh(entry)
    return entry


def _week(client, token, start):
    res = client.get(f"/api/v1/schedule/mine?start={start.isoformat()}&days=14", headers=_h(token))
    assert res.status_code == 200, res.text
    return res.json()


def test_recurring_lecture_appears_every_week_with_source(client, db_session):
    fac = register(client, "sch-fac1@test.com", role="employee")
    _publish(db_session, "sch-fac1@test.com")
    data = _week(client, fac, _monday())
    assert data["has_timetable"] is True
    lectures = [i for i in data["items"] if i["subject"] == "DBMS"]
    assert [i["date"] for i in lectures] == [_monday().isoformat(), (_monday() + timedelta(days=7)).isoformat()]
    assert lectures[0]["class_label"] == "TY C2"
    assert lectures[0]["source"]["filename"] == "ty_c2.docx"


def test_draft_timetable_is_not_shown(client, db_session):
    fac = register(client, "sch-fac2@test.com", role="employee")
    _publish(db_session, "sch-fac2@test.com", status="draft")
    data = _week(client, fac, _monday())
    assert data["items"] == [] and data["has_timetable"] is False


def test_cancellation_affects_only_that_date(client, db_session):
    fac = register(client, "sch-fac3@test.com", role="employee")
    coord = register(client, "sch-coord@test.com", role="manager")
    entry = _publish(db_session, "sch-fac3@test.com")
    res = client.post("/api/v1/schedule/exceptions", headers=_h(coord), json={
        "on_date": _monday().isoformat(), "kind": "cancelled", "entry_id": str(entry.id), "reason": "Exam duty"})
    assert res.status_code == 201, res.text
    statuses = [(i["date"], i["status"]) for i in _week(client, fac, _monday())["items"]]
    assert statuses == [(_monday().isoformat(), "cancelled"), ((_monday() + timedelta(days=7)).isoformat(), "scheduled")]
    # The faculty member is told about it.
    inbox = client.get("/api/v1/notices/mine", headers=_h(fac)).json()
    assert any(n["title"] == "Lecture cancelled" for n in inbox)
    # Cancelling the same occurrence twice is refused.
    again = client.post("/api/v1/schedule/exceptions", headers=_h(coord), json={
        "on_date": _monday().isoformat(), "kind": "cancelled", "entry_id": str(entry.id)})
    assert again.status_code == 400


def test_reschedule_holiday_and_extra(client, db_session):
    fac = register(client, "sch-fac4@test.com", role="employee")
    coord = register(client, "sch-coord2@test.com", role="manager")
    entry = _publish(db_session, "sch-fac4@test.com")
    user = db_session.exec(select(User).where(User.email == "sch-fac4@test.com")).first()
    mon, next_mon = _monday(2), _monday(3)
    assert client.post("/api/v1/schedule/exceptions", headers=_h(coord), json={
        "on_date": mon.isoformat(), "kind": "modified", "entry_id": str(entry.id),
        "start_time": "11:00", "end_time": "12:00", "room": "602"}).status_code == 201
    assert client.post("/api/v1/schedule/exceptions", headers=_h(coord), json={
        "on_date": next_mon.isoformat(), "kind": "holiday", "reason": "Demo holiday (synthetic)"}).status_code == 201
    assert client.post("/api/v1/schedule/exceptions", headers=_h(coord), json={
        "on_date": (mon + timedelta(days=2)).isoformat(), "kind": "extra", "faculty_user_id": str(user.id),
        "start_time": "14:00", "end_time": "15:00", "subject": "DBMS (replacement)", "room": "501"}).status_code == 201
    items = {(i["date"], i["status"]): i for i in _week(client, fac, mon)["items"]}
    moved = items[(mon.isoformat(), "rescheduled")]
    assert (moved["start_time"], moved["room"], moved["original"]["start_time"]) == ("11:00", "602", "09:00")
    assert (next_mon.isoformat(), "holiday") in items
    assert ((mon + timedelta(days=2)).isoformat(), "extra") in items


def test_exception_validation(client, db_session):
    coord = register(client, "sch-coord3@test.com", role="manager")
    register(client, "sch-fac5@test.com", role="employee")
    entry = _publish(db_session, "sch-fac5@test.com")
    tuesday = _monday() + timedelta(days=1)
    wrong_day = client.post("/api/v1/schedule/exceptions", headers=_h(coord), json={
        "on_date": tuesday.isoformat(), "kind": "cancelled", "entry_id": str(entry.id)})
    assert wrong_day.status_code == 400
    bad_time = client.post("/api/v1/schedule/exceptions", headers=_h(coord), json={
        "on_date": _monday().isoformat(), "kind": "modified", "entry_id": str(entry.id), "start_time": "9am"})
    assert bad_time.status_code == 400


def test_only_coordinators_change_schedules(client, db_session):
    fac = register(client, "sch-fac6@test.com", role="employee")
    student = register(client, "sch-stu@test.com", role="student")
    entry = _publish(db_session, "sch-fac6@test.com")
    body = {"on_date": _monday().isoformat(), "kind": "cancelled", "entry_id": str(entry.id)}
    assert client.post("/api/v1/schedule/exceptions", headers=_h(fac), json=body).status_code == 403
    assert client.get("/api/v1/schedule/mine", headers=_h(student)).status_code == 403
