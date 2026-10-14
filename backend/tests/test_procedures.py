"""Procedure governance: versions, publishing to retrieval, visibility/scope, review dates, feedback, export."""
import json
from datetime import date, datetime, timedelta, timezone
from unittest.mock import patch
from uuid import uuid4

from sqlmodel import select

from app.models.structured import Fragment, Skill, SkillVersion, User
from tests.helpers import register


def _h(token):
    return {"Authorization": f"Bearer {token}"}


def _skill(db, **kw):
    s = Skill(
        name=kw.pop("name", f"Revaluation {uuid4().hex[:6]}"), description="How revaluation requests are handled",
        trigger="A student asks for revaluation", steps=json.dumps(["Log the request", "Send to a second examiner"]),
        preconditions=json.dumps(["Within 7 days of results"]), decision_rules=json.dumps(["10% gap: third examiner"]),
        guardrails=json.dumps(["Original examiner never revaluates"]), status=kw.pop("status", "draft"), **kw,
    )
    db.add(s)
    db.commit()
    db.refresh(s)
    return s


def _coord(client, dept=None):
    return _h(register(client, f"proc-coord-{uuid4().hex[:6]}@test.com", "Proc Coord", role="manager", department=dept))


def _frags(db, skill):
    return list(db.exec(select(Fragment).where(Fragment.skill_id == skill.id)))


class TestApproveAndVersions:
    def test_approve_freezes_version_publishes_and_sets_review(self, client, db_session):
        s = _skill(db_session)
        res = client.post(f"/api/v1/skills/{s.id}/approve", json={"owner_office": "Examination Cell"},
                          headers=_coord(client))
        body = res.json()
        assert res.status_code == 200 and body["status"] == "approved" and body["owner_office"] == "Examination Cell"
        assert body["review_by"][:4] == str((datetime.now(timezone.utc) + timedelta(days=365)).year)
        db_session.expire_all()
        assert db_session.exec(select(SkillVersion).where(SkillVersion.skill_id == s.id)).first().version == 1
        frags = _frags(db_session, s)
        assert len(frags) == 1 and frags[0].source_type == "procedure" and frags[0].visibility == "internal"
        assert "Approved procedure" in frags[0].content and "Send to a second examiner" in frags[0].content

    def test_editing_approved_opens_new_version_and_keeps_history(self, client, db_session):
        h = _coord(client)
        s = _skill(db_session)
        client.post(f"/api/v1/skills/{s.id}/approve", headers=h)
        res = client.patch(f"/api/v1/skills/{s.id}", json={"steps": ["Log", "Second examiner", "Publish result"]},
                           headers=h).json()
        assert res["status"] == "draft" and res["version"] == 2
        assert _frags(db_session, s)  # v1 stays searchable until v2 is approved
        client.post(f"/api/v1/skills/{s.id}/approve", headers=h)
        versions = client.get(f"/api/v1/skills/{s.id}/versions", headers=h).json()["versions"]
        assert [v["version"] for v in versions] == [2, 1]
        assert versions[0]["snapshot"]["steps"][-1] == "Publish result"
        db_session.expire_all()
        assert len(_frags(db_session, s)) == 1 and "v2" in _frags(db_session, s)[0].source_ref

    def test_settings_only_edit_keeps_approval(self, client, db_session):
        h = _coord(client)
        s = _skill(db_session)
        client.post(f"/api/v1/skills/{s.id}/approve", headers=h)
        res = client.patch(f"/api/v1/skills/{s.id}", json={"owner_office": "Exam Cell", "category": "examinations"},
                           headers=h).json()
        assert res["status"] == "approved" and res["version"] == 1 and res["category"] == "examinations"

    def test_approve_needs_steps(self, client, db_session):
        s = _skill(db_session)
        s.steps = "[]"
        db_session.add(s)
        db_session.commit()
        assert client.post(f"/api/v1/skills/{s.id}/approve", headers=_coord(client)).status_code == 400


class TestRejectRetireStale:
    def test_reject_requires_reason(self, client, db_session):
        h = _coord(client)
        s = _skill(db_session)
        assert client.post(f"/api/v1/skills/{s.id}/reject", json={"reason": ""}, headers=h).status_code == 400
        res = client.post(f"/api/v1/skills/{s.id}/reject", json={"reason": "Duplicates the exam SOP"}, headers=h).json()
        assert res["status"] == "rejected" and res["reject_reason"] == "Duplicates the exam SOP"

    def test_retire_unpublishes(self, client, db_session):
        h = _coord(client)
        s = _skill(db_session)
        client.post(f"/api/v1/skills/{s.id}/approve", headers=h)
        assert client.post(f"/api/v1/skills/{s.id}/retire", headers=h).json()["status_label"] == "Retired"
        db_session.expire_all()
        assert _frags(db_session, s) == []

    def test_freshness_records_reason_and_evidence_and_unpublishes(self, db_session):
        from app.services.freshness_service import freshness_service
        from app.services.procedure_service import procedure_service

        s = _skill(db_session)
        procedure_service.approve(db_session, s, "tester")
        ev = Fragment(source_type="transcript", source_ref="Exam meeting", content="Revaluation now goes to two examiners")
        with patch.object(freshness_service, "_detect_contradiction", return_value={"contradicts": True, "reason": "Rule changed"}):
            freshness_service._flag_stale(db_session, s, "Rule changed", [ev])
        db_session.refresh(s)
        assert s.status == "stale" and s.stale_reason == "Rule changed"
        assert json.loads(s.stale_evidence)[0]["source_ref"] == "Exam meeting"
        assert _frags(db_session, s) == []

    def test_repeated_wrong_feedback_flags_for_review(self, client, db_session):
        h = _coord(client)
        s = _skill(db_session)
        client.post(f"/api/v1/skills/{s.id}/approve", headers=h)
        last = None
        for i in range(3):
            last = client.post(f"/api/v1/skills/{s.id}/feedback", json={"outcome": "wrong", "detail": f"#{i}"},
                               headers=_h(register(client, f"proc-fb-{uuid4().hex[:6]}@test.com"))).json()
        assert last["flagged_for_review"] is True and last["feedback"]["wrong"] == 3
        db_session.expire_all()
        assert db_session.get(Skill, s.id).status == "stale"


class TestVisibilityAndScope:
    def test_student_summary_published_as_public(self, client, db_session):
        h = _coord(client)
        s = _skill(db_session, visibility="public", student_summary="Apply within 7 days of results at the Exam Cell.")
        client.post(f"/api/v1/skills/{s.id}/approve", headers=h)
        db_session.expire_all()
        vis = sorted(f.visibility for f in _frags(db_session, s))
        assert vis == ["internal", "public"]
        public = next(f for f in _frags(db_session, s) if f.visibility == "public")
        assert "Send to a second examiner" not in public.content  # internal steps never reach students
        stu = _h(register(client, f"proc-stu-{uuid4().hex[:6]}@test.com", role="student"))
        listed = client.get("/api/v1/skills/student", headers=stu).json()
        assert any(p["id"] == str(s.id) and "7 days" in p["summary"] for p in listed)
        assert client.get("/api/v1/skills", headers=stu).status_code == 403

    def test_department_scope(self, client, db_session):
        s = _skill(db_session, department="CE")
        it = _h(register(client, f"proc-it-{uuid4().hex[:6]}@test.com", role="employee", department="IT"))
        ids = {x["id"] for x in client.get("/api/v1/skills", headers=it).json()}
        assert str(s.id) not in ids
        assert client.get(f"/api/v1/skills/{s.id}", headers=it).status_code == 404

    def test_invalid_settings(self, client, db_session):
        h = _coord(client)
        s = _skill(db_session)
        assert client.patch(f"/api/v1/skills/{s.id}", json={"visibility": "secret"}, headers=h).status_code == 400
        assert client.patch(f"/api/v1/skills/{s.id}", json={"category": "astrology"}, headers=h).status_code == 400


class TestManualAndExport:
    def test_manual_create_is_a_draft(self, client, db_session):
        res = client.post("/api/v1/skills", json={"name": "Issue a bonafide certificate",
                                                  "steps": ["Student applies", "Office verifies", "Principal signs"],
                                                  "owner_office": "Administrative Office"}, headers=_coord(client))
        body = res.json()
        assert res.status_code == 201 and body["status"] == "draft" and body["origin"] == "manual"
        assert body["steps"][-1] == "Principal signs"

    def test_export_and_handbook(self, client, db_session):
        h = _coord(client)
        s = _skill(db_session, name="Handbook entry")
        client.post(f"/api/v1/skills/{s.id}/approve", headers=h)
        pdf = client.get(f"/api/v1/skills/{s.id}/export?format=pdf", headers=h)
        assert pdf.status_code == 200 and pdf.content.startswith(b"%PDF")
        docx = client.get(f"/api/v1/skills/{s.id}/export?format=docx", headers=h)
        assert docx.status_code == 200 and "wordprocessingml" in docx.headers["content-type"]
        book = client.get("/api/v1/skills/handbook?format=pdf", headers=h)
        assert book.status_code == 200 and book.content.startswith(b"%PDF")


class TestRetrievalAndUse:
    def test_procedure_leads_when_close_enough(self):
        from app.services.rag_service import rag_service

        class Coll:
            def query(self, **kw):
                if kw["where"] == {"source_type": "procedure"}:
                    return {"documents": [["Approved procedure: Revaluation…"]],
                            "metadatas": [[{"source_type": "procedure", "visibility": "internal", "department": "all",
                                            "skill_id": "abc"}]], "distances": [[0.2]]}
                return {"documents": [["meeting line a", "meeting line b", "meeting line c"]],
                        "metadatas": [[{"source_type": "transcript"}] * 3], "distances": [[0.1, 0.25, 0.3]]}

        with patch("app.core.chroma_db.chroma_conn") as conn, patch("app.services.embedding.embedding_service") as emb:
            conn.collection = Coll()
            emb.is_available = True
            emb.embed_texts.return_value = [[0.1]]
            sources = rag_service.retrieve("revaluation?", public_only=False)
        assert sources[0]["source_type"] == "procedure" and sources[0]["skill_id"] == "abc"

    def test_far_procedure_does_not_lead(self):
        from app.services.rag_service import rag_service

        class Coll:
            def query(self, **kw):
                if kw["where"] == {"source_type": "procedure"}:
                    return {"documents": [["Approved procedure: Unrelated"]],
                            "metadatas": [[{"source_type": "procedure"}]], "distances": [[0.9]]}
                return {"documents": [["a", "b", "c"]], "metadatas": [[{}] * 3], "distances": [[0.1, 0.2, 0.3]]}

        with patch("app.core.chroma_db.chroma_conn") as conn, patch("app.services.embedding.embedding_service") as emb:
            conn.collection = Coll()
            emb.is_available = True
            emb.embed_texts.return_value = [[0.1]]
            sources = rag_service.retrieve("q", public_only=False)
        assert all(s["source_type"] != "procedure" for s in sources)

    def test_use_is_counted(self, db_session):
        from app.services.procedure_service import procedure_service

        s = _skill(db_session)
        procedure_service.record_use(db_session, {str(s.id), "not-a-uuid"})
        db_session.refresh(s)
        assert s.use_count == 1


class TestReviewDates:
    def test_owner_sees_review_on_calendar(self, db_session):
        from app.models.structured import Employee
        from app.services.calendar_service import calendar_service

        user = User(email=f"proc-owner-{uuid4().hex[:6]}@test.com", hashed_password="x", role="employee")
        db_session.add(user)
        db_session.commit()
        emp = Employee(display_name="Owner", user_id=user.id)
        db_session.add(emp)
        db_session.commit()
        _skill(db_session, name="Review me", status="approved", owner_employee_id=emp.id,
               review_by=datetime(2026, 10, 22, tzinfo=timezone.utc))
        items = calendar_service.reviews_for(db_session, user, today=date(2026, 10, 20), days=30)
        assert items[0]["title"] == "Review procedure: Review me" and items[0]["urgency"] == "soon"
