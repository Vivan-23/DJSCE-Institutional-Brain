"""The one assistant box: routing, work updates with undo, and answers."""
from unittest.mock import MagicMock, patch

from sqlmodel import select

from app.models.structured import Commitment, User
from app.services.assistant_service import _keyword_route
from app.services.employee_service import employee_service
from tests.helpers import register

OFF = MagicMock(is_available=False)  # no language model: keyword routing


def _auth(token):
    return {"Authorization": f"Bearer {token}"}


def _task(db, email, description="Correct the C31 ML lab files"):
    user = db.exec(select(User).where(User.email == email)).first()
    emp = employee_service.get_or_create_for_user(db, user)
    c = Commitment(description=description, status="open", assignee_employee_id=emp.id, progress=10,
                   remaining="20 files")
    db.add(c)
    db.commit()
    db.refresh(c)
    return c


class TestKeywordRouting:
    def test_question(self):
        r = _keyword_route("When is term test 2?")
        assert r["question"] and not r["update"] and not r["schedule"]

    def test_update(self):
        r = _keyword_route("Finished the C31 lab marks today")
        assert r["update"] and not r["question"]

    def test_own_classes(self):
        assert _keyword_route("What are my classes tomorrow?")["schedule"] == "tomorrow"

    def test_update_and_question_together(self):
        r = _keyword_route("Finished the lab marks. When is the TT2 paper due?")
        assert r["update"] and r["question"]


def test_question_is_answered_with_sources(client):
    token = register(client, "as.q@test.com", role="employee")
    with patch("app.services.assistant_service.llm_service", OFF):
        res = client.post("/api/v1/assistant/message", headers=_auth(token), json={"text": "What is the leave procedure?"})
    assert res.status_code == 200
    body = res.json()
    assert body["reply"] and body["updates"] == []
    assert body["plan"]["question"]


def test_update_changes_task_and_undo_restores_it(client, db_session):
    email = "as.u@test.com"
    token = register(client, email, role="employee")
    c = _task(db_session, email)
    pa_llm = MagicMock(is_available=True)
    pa_llm.complete_json.return_value = {
        "reply": "Great work!", "new_commitments": [],
        "updates": [{"commitment_id": str(c.id), "status": "done", "progress": 100, "summary": "files corrected"}],
    }
    with patch("app.services.assistant_service.llm_service", OFF), patch("app.services.pa_service.llm_service", pa_llm):
        res = client.post("/api/v1/assistant/message", headers=_auth(token),
                          json={"text": "Finished correcting the C31 lab files"})
    assert res.status_code == 200
    upd = res.json()["updates"][0]
    assert upd["status"] == "review" and upd["before"]["status"] == "open" and upd["before"]["progress"] == 10

    res = client.post("/api/v1/assistant/undo", headers=_auth(token),
                      json={"commitment_id": upd["commitment_id"], "before": upd["before"]})
    assert res.status_code == 200
    db_session.expire_all()
    back = db_session.get(Commitment, c.id)
    assert (back.status, back.progress, back.remaining) == ("open", 10, "20 files")


def test_undo_new_task_drops_it(client, db_session):
    email = "as.n@test.com"
    token = register(client, email, role="employee")
    _task(db_session, email)
    pa_llm = MagicMock(is_available=True)
    pa_llm.complete_json.return_value = {"reply": "Noted", "updates": [],
                                         "new_commitments": [{"description": "Set the BIA paper"}]}
    with patch("app.services.assistant_service.llm_service", OFF), patch("app.services.pa_service.llm_service", pa_llm):
        res = client.post("/api/v1/assistant/message", headers=_auth(token), json={"text": "Started setting the BIA paper"})
    new = res.json()["updates"][0]
    assert new["new"] and new["description"] == "Set the BIA paper"
    res = client.post("/api/v1/assistant/undo", headers=_auth(token), json={"commitment_id": new["commitment_id"], "new": True})
    assert res.status_code == 200 and res.json()["status"] == "dropped"


def test_cannot_undo_someone_elses_task(client, db_session):
    owner = "as.owner@test.com"
    register(client, owner, role="employee")
    c = _task(db_session, owner)
    other = register(client, "as.other@test.com", role="employee")
    res = client.post("/api/v1/assistant/undo", headers=_auth(other),
                      json={"commitment_id": str(c.id), "before": {"status": "open", "progress": 0}})
    assert res.status_code == 404


def test_students_only_get_answers(client, db_session):
    token = register(client, "as.s@test.com", role="student")
    with patch("app.services.assistant_service.llm_service", OFF):
        res = client.post("/api/v1/assistant/message", headers=_auth(token), json={"text": "Finished my assignment"})
    assert res.status_code == 200
    assert res.json()["updates"] == [] and res.json()["plan"]["question"]
    assert client.post("/api/v1/assistant/undo", headers=_auth(token),
                       json={"commitment_id": "00000000-0000-0000-0000-000000000001", "new": True}).status_code == 403


def test_my_classes_without_a_timetable(client):
    token = register(client, "as.t@test.com", role="employee")
    with patch("app.services.assistant_service.llm_service", OFF):
        res = client.post("/api/v1/assistant/message", headers=_auth(token), json={"text": "What are my classes today?"})
    assert res.status_code == 200
    assert "No teaching timetable" in res.json()["reply"]


def test_two_logins_with_the_same_name_get_separate_profiles(client, db_session):
    register(client, "same.a@test.com", "Asha Rao", role="employee")
    register(client, "same.b@test.com", "Asha Rao", role="employee")
    users = db_session.exec(select(User).where(User.full_name == "Asha Rao")).all()
    a, b = (employee_service.get_or_create_for_user(db_session, u) for u in users)
    assert a.id != b.id
