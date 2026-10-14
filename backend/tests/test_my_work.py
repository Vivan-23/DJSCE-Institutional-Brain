"""Task tracking: My Work, owner-only progress, mark done → confirm / send back, scoping, check-in progress."""
from datetime import datetime, timedelta, timezone
from unittest.mock import patch
from uuid import UUID, uuid4

from sqlmodel import select

from app.models.structured import Commitment, Meeting, Notice, NoticeRecipient, User
from app.services.employee_service import employee_service
from tests.helpers import register


def _h(token):
    return {"Authorization": f"Bearer {token}"}


def _user(db, email):
    return db.exec(select(User).where(User.email == email)).first()


def _staff(client, db, role="employee", department="CE"):
    email = f"mw-{role}-{uuid4().hex[:6]}@test.com"
    token = register(client, email, f"MW {role}", role=role, department=department)
    return _h(token), _user(db, email)


def _task(db, owner: User, *, department="CE", status="open", due_days=None, description=None):
    emp = employee_service.get_or_create_for_user(db, owner)
    c = Commitment(
        assignee_employee_id=emp.id, description=description or f"Task {uuid4().hex[:6]}", status=status,
        department=department,
        due_date=(datetime.now(timezone.utc) + timedelta(days=due_days)) if due_days is not None else None,
    )
    db.add(c)
    db.commit()
    db.refresh(c)
    return c


def _notices_for(db, user):
    ids = [r.notice_id for r in db.exec(select(NoticeRecipient).where(NoticeRecipient.user_id == user.id))]
    return [db.get(Notice, i).title for i in ids]


class TestMyWork:
    def test_summary_and_items(self, client, db_session):
        h, me = _staff(client, db_session)
        _task(db_session, me, due_days=-2)  # overdue
        _task(db_session, me, due_days=3)
        _task(db_session, me, status="done")
        body = client.get("/api/v1/commitments/my-work", headers=h).json()
        assert body["summary"]["open"] == 2 and body["summary"]["overdue"] == 1
        assert body["summary"]["due_this_week"] == 1 and body["summary"]["completed"] == 1
        assert all(i["can_update"] for i in body["items"])
        assert "awaiting_my_confirmation" not in body  # faculty

    def test_detail_has_timeline_and_source_line(self, client, db_session):
        from app.models.structured import Fragment

        h, me = _staff(client, db_session)
        emp = employee_service.get_or_create_for_user(db_session, me)
        m = Meeting(title="Lab sync", occurred_at=datetime.now(timezone.utc), department="CE")
        db_session.add(m)
        db_session.commit()
        db_session.add(Fragment(source_type="transcript", content="I will replace the network switch in Lab 4 by Friday.",
                                meeting_id=m.id, author_employee_id=emp.id))
        c = Commitment(assignee_employee_id=emp.id, description="Replace the network switch in Lab 4",
                       source_meeting_id=m.id, department="CE")
        db_session.add(c)
        db_session.commit()
        client.post(f"/api/v1/commitments/{c.id}/progress", json={"progress": 40, "note": "switch ordered"}, headers=h)
        d = client.get(f"/api/v1/commitments/{c.id}", headers=h).json()
        assert d["source_meeting"] == "Lab sync"
        assert "network switch" in d["source_line"]["text"]
        assert d["timeline"][-1]["text"] == "switch ordered" and d["timeline"][-1]["progress"] == 40


class TestOwnerRules:
    def test_owner_updates_progress_and_others_cannot(self, client, db_session):
        h, me = _staff(client, db_session)
        other_h, _ = _staff(client, db_session)
        c = _task(db_session, me)
        res = client.post(f"/api/v1/commitments/{c.id}/progress",
                          json={"progress": 60, "remaining": "2 sets left"}, headers=h).json()
        assert res["progress"] == 60 and res["status"] == "in_progress" and res["remaining"] == "2 sets left"
        assert client.post(f"/api/v1/commitments/{c.id}/progress", json={"progress": 90},
                           headers=other_h).status_code == 403
        assert client.patch(f"/api/v1/commitments/{c.id}", json={"status": "blocked"},
                            headers=other_h).status_code == 403

    def test_blocked_needs_reason(self, client, db_session):
        h, me = _staff(client, db_session)
        c = _task(db_session, me)
        assert client.post(f"/api/v1/commitments/{c.id}/progress", json={"status": "blocked"},
                           headers=h).status_code == 400
        res = client.post(f"/api/v1/commitments/{c.id}/progress",
                          json={"status": "blocked", "blocked_reason": "waiting on the vendor"}, headers=h).json()
        assert res["status"] == "blocked" and res["blocked_reason"] == "waiting on the vendor"

    def test_owner_cannot_set_done_directly(self, client, db_session):
        h, me = _staff(client, db_session)
        c = _task(db_session, me)
        assert client.patch(f"/api/v1/commitments/{c.id}", json={"status": "done"}, headers=h).status_code == 403


class TestConfirmation:
    def test_mark_done_then_confirm(self, client, db_session):
        h, me = _staff(client, db_session)
        coord_h, coord = _staff(client, db_session, role="manager")
        c = _task(db_session, me)
        c.assigned_by_user_id = coord.id
        db_session.add(c)
        db_session.commit()
        res = client.post(f"/api/v1/commitments/{c.id}/done", headers=h).json()
        assert res["status"] == "review" and res["progress"] == 100
        assert any("Ready to confirm" in t for t in _notices_for(db_session, coord))
        waiting = client.get("/api/v1/commitments/my-work", headers=coord_h).json()["awaiting_my_confirmation"]
        assert any(w["id"] == str(c.id) for w in waiting)
        assert client.post(f"/api/v1/commitments/{c.id}/confirm", headers=h).status_code == 403  # owner can't
        done = client.post(f"/api/v1/commitments/{c.id}/confirm", headers=coord_h).json()
        assert done["status"] == "done" and done["confirmed_by"] == "MW manager"
        assert any("completed" in t.lower() for t in _notices_for(db_session, me))

    def test_send_back(self, client, db_session):
        h, me = _staff(client, db_session)
        coord_h, _ = _staff(client, db_session, role="manager")
        c = _task(db_session, me)
        client.post(f"/api/v1/commitments/{c.id}/done", headers=h)
        assert client.post(f"/api/v1/commitments/{c.id}/send-back", json={"comment": " "},
                           headers=coord_h).status_code in (400, 422)
        res = client.post(f"/api/v1/commitments/{c.id}/send-back", json={"comment": "Add the IT batch rosters"},
                          headers=coord_h).json()
        assert res["status"] == "in_progress" and res["remaining"] == "Add the IT batch rosters"
        assert any("sent back" in t.lower() for t in _notices_for(db_session, me))

    def test_confirm_requires_review(self, client, db_session):
        _, me = _staff(client, db_session)
        coord_h, _ = _staff(client, db_session, role="manager")
        c = _task(db_session, me)
        assert client.post(f"/api/v1/commitments/{c.id}/confirm", headers=coord_h).status_code == 400


class TestCoordinatorTools:
    def test_create_task_and_notify(self, client, db_session):
        coord_h, _ = _staff(client, db_session, role="manager")
        h, me = _staff(client, db_session, department="IT")
        due = (datetime.now(timezone.utc) + timedelta(days=5)).isoformat()
        res = client.post("/api/v1/commitments", json={"description": "Prepare NAAC criterion 2 evidence",
                                                        "assignee_user_id": str(me.id), "due_date": due,
                                                        "notes": "Use last year's format"}, headers=coord_h)
        assert res.status_code == 201
        body = res.json()
        assert body["assigned_by"] == "MW manager" and body["department"] == "IT"
        assert any("New task" in t for t in _notices_for(db_session, me))
        mine = client.get("/api/v1/commitments/my-work", headers=h).json()["items"]
        assert any(i["id"] == body["id"] for i in mine)
        # faculty can't create
        assert client.post("/api/v1/commitments", json={"description": "x", "assignee_user_id": str(me.id)},
                           headers=h).status_code == 403

    def test_team_view_groups_by_owner(self, client, db_session):
        coord_h, _ = _staff(client, db_session, role="admin")
        _, a = _staff(client, db_session)
        _task(db_session, a, due_days=-1)
        groups = client.get("/api/v1/commitments/team", headers=coord_h).json()
        assert any(g["owner"] == a.full_name and g["summary"]["overdue"] >= 1 for g in groups)

    def test_reassign_and_due_date(self, client, db_session):
        coord_h, _ = _staff(client, db_session, role="manager")
        _, a = _staff(client, db_session)
        _, b = _staff(client, db_session)
        c = _task(db_session, a)
        new_due = (datetime.now(timezone.utc) + timedelta(days=10)).isoformat()
        res = client.patch(f"/api/v1/commitments/{c.id}", json={"assignee_user_id": str(b.id), "due_date": new_due},
                           headers=coord_h).json()
        assert res["assignee"] == b.full_name and res["due_date"].startswith(new_due[:10])


class TestScope:
    def test_list_is_department_scoped(self, client, db_session):
        it_h, _ = _staff(client, db_session, department="IT")
        _, ce_owner = _staff(client, db_session, department="CE")
        ce_task = _task(db_session, ce_owner, department="CE")
        ids = {i["id"] for i in client.get("/api/v1/commitments", headers=it_h).json()}
        assert str(ce_task.id) not in ids
        assert client.get(f"/api/v1/commitments/{ce_task.id}", headers=it_h).status_code == 404


class TestCheckinProgress:
    def test_checkin_updates_progress_remaining_and_review(self, client, db_session):
        h, me = _staff(client, db_session)
        c1 = _task(db_session, me, description="Moderate the five question paper sets")
        c2 = _task(db_session, me, description="Send examiner list")
        parsed = {"reply": "Nice work!", "new_commitments": [], "updates": [
            {"commitment_id": str(c1.id), "status": "in_progress", "summary": "3 of 5 sets moderated",
             "progress": "60%", "remaining": "2 sets", "blocker": None},
            {"commitment_id": str(c2.id), "status": "done", "summary": "sent", "progress": 100},
        ]}
        with patch("app.services.pa_service.PAService._extract_checkin", return_value=parsed):
            res = client.post("/api/v1/pa/checkin/message", json={"text": "moderated 3 sets, sent the list"},
                              headers=h).json()
        db_session.expire_all()
        a, b = db_session.get(Commitment, c1.id), db_session.get(Commitment, c2.id)
        assert (a.progress, a.remaining, a.status) == (60, "2 sets", "in_progress")
        assert b.status == "review"  # "done" from a check-in still needs confirmation
        assert any(u.get("progress") == 60 for u in res["updates"])

    def test_percent_parsing(self):
        from app.services.pa_service import _percent

        assert _percent("60%") == 60 and _percent(140) == 100 and _percent(None) is None and _percent("lots") is None
