"""Notices: audience filters, sender rules, inbox, read tracking, expiry."""
from datetime import datetime, timedelta, timezone
from uuid import uuid4

from sqlmodel import select

from app.models.structured import AuditLog, User
from tests.helpers import register


def _h(token):
    return {"Authorization": f"Bearer {token}"}


TAG = uuid4().hex[:6]
COHORT = [  # (key, department, year, semester, division)
    ("ce3a", "CE", 3, 5, "A"), ("ce3b", "CE", 3, 5, "B"), ("ce1a", "CE", 1, 1, "A"),
    ("it2a", "IT", 2, 3, "A"), ("it4a", "IT", 4, 7, "A"),
]


def _cohort(db):
    """Students of this test module, distinguishable by a unique division suffix-free tag in the email."""
    out = {}
    for key, dept, year, sem, div in COHORT:
        email = f"n-{key}-{TAG}@test.com"
        user = db.exec(select(User).where(User.email == email)).first()
        if not user:
            user = User(email=email, hashed_password="x", role="student", department=dept,
                        year=year, semester=sem, division=div)
            db.add(user)
            db.commit()
            db.refresh(user)
        out[key] = user
    return out


def _ids(db, notice_id):
    from app.models.structured import NoticeRecipient

    return {r.user_id for r in db.exec(select(NoticeRecipient).where(NoticeRecipient.notice_id == notice_id))}


class TestAudience:
    def test_filters_combine(self, client, db_session):
        c = _cohort(db_session)
        coord = _h(register(client, f"n-coord-{TAG}@test.com", role="manager"))
        res = client.post("/api/v1/notices", json={
            "title": "TE CE", "body": "Lab schedule", "audience": {"departments": ["CE"], "years": [3]}}, headers=coord)
        assert res.status_code == 201
        got = _ids(db_session, __import__("uuid").UUID(res.json()["id"]))
        assert {c["ce3a"].id, c["ce3b"].id} <= got and c["ce1a"].id not in got and c["it2a"].id not in got

        res = client.post("/api/v1/notices", json={
            "title": "Div A", "body": "x", "audience": {"departments": ["CE", "IT"], "divisions": ["a"]}}, headers=coord)
        got = _ids(db_session, __import__("uuid").UUID(res.json()["id"]))
        assert {c["ce3a"].id, c["ce1a"].id, c["it2a"].id, c["it4a"].id} <= got and c["ce3b"].id not in got

    def test_preview_counts(self, client, db_session):
        _cohort(db_session)
        coord = _h(register(client, f"n-coord2-{TAG}@test.com", role="admin"))
        body = client.post("/api/v1/notices/preview", json={"departments": ["IT"], "semesters": [7]}, headers=coord).json()
        assert body["count"] >= 1 and body["audience"]["departments"] == ["IT"]

    def test_bad_audience(self, client):
        coord = _h(register(client, f"n-coord3-{TAG}@test.com", role="manager"))
        for aud in ({"departments": ["Astrology"]}, {"years": [6]}, {"roles": ["god"]}):
            res = client.post("/api/v1/notices", json={"title": "t", "body": "b", "audience": aud}, headers=coord)
            assert res.status_code in (400, 422), aud

    def test_empty_audience_is_rejected(self, client):
        coord = _h(register(client, f"n-coord4-{TAG}@test.com", role="manager"))
        res = client.post("/api/v1/notices", json={"title": "t", "body": "b",
                                                    "audience": {"departments": ["MECH"], "divisions": ["Z"]}}, headers=coord)
        assert res.status_code == 400 and "No one" in res.json()["detail"]


class TestSenderRules:
    def test_students_cannot_send(self, client):
        stu = _h(register(client, f"n-stu-{TAG}@test.com", role="student", department="CE"))
        assert client.post("/api/v1/notices", json={"title": "t", "body": "b"}, headers=stu).status_code == 403

    def test_faculty_limited_to_own_department(self, client, db_session):
        c = _cohort(db_session)
        fac = _h(register(client, f"n-fac-{TAG}@test.com", role="employee", department="CE"))
        bad = client.post("/api/v1/notices", json={"title": "t", "body": "b", "audience": {"departments": ["IT"]}},
                          headers=fac)
        assert bad.status_code == 400
        ok = client.post("/api/v1/notices", json={"title": "CE only", "body": "b"}, headers=fac)  # no filter → own dept
        got = _ids(db_session, __import__("uuid").UUID(ok.json()["id"]))
        assert c["ce1a"].id in got and c["it2a"].id not in got

    def test_faculty_without_department_cannot_send(self, client):
        fac = _h(register(client, f"n-fac2-{TAG}@test.com", role="employee"))
        assert client.post("/api/v1/notices", json={"title": "t", "body": "b"}, headers=fac).status_code == 400

    def test_send_is_audited(self, client, db_session):
        _cohort(db_session)
        coord = _h(register(client, f"n-coord5-{TAG}@test.com", role="manager"))
        client.post("/api/v1/notices", json={"title": "Audited", "body": "b", "audience": {"departments": ["CE"]}},
                    headers=coord)
        assert db_session.exec(select(AuditLog).where(AuditLog.action == "notice_send")).first()


class TestInbox:
    def test_inbox_read_tracking_and_sent_counts(self, client, db_session):
        coord = _h(register(client, f"n-coord6-{TAG}@test.com", role="manager"))
        stu_email = f"n-reader-{TAG}@test.com"
        stu = _h(register(client, stu_email, role="student", department="IT"))
        other = _h(register(client, f"n-other-{TAG}@test.com", role="student", department="CE"))
        sent = client.post("/api/v1/notices", json={"title": "Urgent IT", "body": "Read me", "priority": "urgent",
                                                     "audience": {"departments": ["IT"]}}, headers=coord).json()
        mine = client.get("/api/v1/notices/mine", headers=stu).json()
        assert mine[0]["title"] == "Urgent IT" and mine[0]["read"] is False
        assert client.get("/api/v1/notices/unread-count", headers=stu).json()["unread"] >= 1
        assert all(n["id"] != sent["id"] for n in client.get("/api/v1/notices/mine", headers=other).json())
        assert client.post(f"/api/v1/notices/{sent['id']}/read", headers=other).status_code == 404  # not addressed
        assert client.post(f"/api/v1/notices/{sent['id']}/read", headers=stu).status_code == 200
        assert next(n for n in client.get("/api/v1/notices/mine", headers=stu).json() if n["id"] == sent["id"])["read"]
        row = next(n for n in client.get("/api/v1/notices/sent", headers=coord).json() if n["id"] == sent["id"])
        assert row["read"] == 1 and row["recipients"] >= 1

    def test_expired_notices_disappear(self, client, db_session):
        from app.models.structured import Notice

        coord = _h(register(client, f"n-coord7-{TAG}@test.com", role="manager"))
        stu = _h(register(client, f"n-exp-{TAG}@test.com", role="student", department="IT"))
        soon = (datetime.now(timezone.utc) + timedelta(hours=1)).isoformat()
        nid = client.post("/api/v1/notices", json={"title": "Expiring", "body": "b", "expires_at": soon,
                                                    "audience": {"departments": ["IT"]}}, headers=coord).json()["id"]
        n = db_session.get(Notice, __import__("uuid").UUID(nid))
        n.expires_at = datetime.now(timezone.utc) - timedelta(minutes=1)
        db_session.add(n)
        db_session.commit()
        assert all(x["id"] != nid for x in client.get("/api/v1/notices/mine", headers=stu).json())

    def test_past_expiry_rejected(self, client):
        coord = _h(register(client, f"n-coord8-{TAG}@test.com", role="manager"))
        past = (datetime.now(timezone.utc) - timedelta(days=1)).isoformat()
        res = client.post("/api/v1/notices", json={"title": "t", "body": "b", "expires_at": past}, headers=coord)
        assert res.status_code == 400

    def test_deactivated_users_are_not_addressed(self, client, db_session):
        u = User(email=f"n-inactive-{TAG}@test.com", hashed_password="x", role="student", department="BSH",
                 is_active=False)
        db_session.add(u)
        db_session.commit()
        coord = _h(register(client, f"n-coord9-{TAG}@test.com", role="manager"))
        res = client.post("/api/v1/notices", json={"title": "t", "body": "b", "audience": {"departments": ["BSH"]}},
                          headers=coord)
        assert res.status_code == 400  # the only BSH student is inactive → no one matches
