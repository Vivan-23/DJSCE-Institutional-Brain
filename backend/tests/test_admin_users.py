"""Admin user management: create, edit, deactivate, reset password, CSV import, guardrails."""
from uuid import uuid4

from sqlmodel import select

from app.models.structured import AuditLog, Employee, User
from tests.helpers import register


def _h(token):
    return {"Authorization": f"Bearer {token}"}


def _admin(client):
    return _h(register(client, f"admin-{uuid4().hex[:6]}@test.com", role="admin"))


def _email(prefix="u"):
    return f"{prefix}-{uuid4().hex[:8]}@test.com"


class TestAccess:
    def test_only_admins(self, client):
        for role in ("student", "employee", "manager"):
            h = _h(register(client, f"notadmin-{role}@test.com", role=role))
            assert client.get("/api/v1/admin/users", headers=h).status_code == 403
            assert client.post("/api/v1/admin/users", json={"email": _email()}, headers=h).status_code == 403

    def test_role_table(self, client):
        body = client.get("/api/v1/admin/roles", headers=_admin(client)).json()
        assert body["roles"] == ["student", "employee", "manager", "admin"]
        assert any(p["capability"] == "Manage users" and p["roles"] == ["admin"] for p in body["permissions"])


class TestCreateAndEdit:
    def test_create_student_with_generated_password_and_log_in(self, client, db_session):
        email = _email("stu")
        res = client.post("/api/v1/admin/users", json={
            "email": email, "full_name": "New Student", "department": "Information Technology",
            "year": 2, "semester": 4, "division": "b",
        }, headers=_admin(client))
        assert res.status_code == 201
        body = res.json()
        assert body["department"] == "IT" and body["division"] == "B" and body["role"] == "student"
        pw = body["temporary_password"]
        assert pw and client.post("/api/v1/auth/login", json={"email": email, "password": pw}).status_code == 200
        assert db_session.exec(select(AuditLog).where(AuditLog.action == "user_create")).first()

    def test_staff_get_an_employee_profile(self, client, db_session):
        res = client.post("/api/v1/admin/users", json={"email": _email("fac"), "full_name": "Prof. New",
                                                       "role": "employee", "password": "secret12"}, headers=_admin(client))
        assert res.status_code == 201 and res.json()["temporary_password"] is None
        user = db_session.get(User, __import__("uuid").UUID(res.json()["id"]))
        assert db_session.exec(select(Employee).where(Employee.user_id == user.id)).first() is not None

    def test_validation(self, client):
        h = _admin(client)
        for bad in ({"email": "not-an-email"}, {"email": _email(), "role": "superuser"},
                    {"email": _email(), "department": "Astrology"}, {"email": _email(), "year": 5},
                    {"email": _email(), "year": 1, "semester": 6}, {"email": _email(), "password": "123"}):
            assert client.post("/api/v1/admin/users", json=bad, headers=h).status_code == 400, bad

    def test_duplicate_email(self, client):
        h, email = _admin(client), _email()
        assert client.post("/api/v1/admin/users", json={"email": email}, headers=h).status_code == 201
        assert client.post("/api/v1/admin/users", json={"email": email}, headers=h).status_code == 400

    def test_promote_student_to_faculty(self, client):
        h, email = _admin(client), _email("promo")
        uid = client.post("/api/v1/admin/users", json={"email": email}, headers=h).json()["id"]
        res = client.patch(f"/api/v1/admin/users/{uid}", json={"role": "employee", "department": "CE"}, headers=h)
        assert res.status_code == 200 and res.json()["role"] == "employee" and res.json()["department"] == "CE"

    def test_filters(self, client):
        h = _admin(client)
        client.post("/api/v1/admin/users", json={"email": _email("filt"), "full_name": "Filter Target",
                                                 "department": "IT"}, headers=h)
        found = client.get("/api/v1/admin/users?q=filter target&department=IT&role=student", headers=h).json()
        assert [u["full_name"] for u in found] == ["Filter Target"]


class TestDeactivationAndPasswords:
    def test_deactivated_user_cannot_log_in_or_use_token(self, client):
        h, email = _admin(client), _email("deact")
        created = client.post("/api/v1/admin/users", json={"email": email, "password": "secret12"}, headers=h).json()
        token = client.post("/api/v1/auth/login", json={"email": email, "password": "secret12"}).json()["access_token"]
        client.patch(f"/api/v1/admin/users/{created['id']}", json={"is_active": False}, headers=h)
        assert client.post("/api/v1/auth/login", json={"email": email, "password": "secret12"}).status_code == 403
        assert client.get("/api/v1/auth/me", headers=_h(token)).status_code == 401
        client.patch(f"/api/v1/admin/users/{created['id']}", json={"is_active": True}, headers=h)
        assert client.post("/api/v1/auth/login", json={"email": email, "password": "secret12"}).status_code == 200

    def test_reset_password(self, client):
        h, email = _admin(client), _email("reset")
        uid = client.post("/api/v1/admin/users", json={"email": email, "password": "secret12"}, headers=h).json()["id"]
        pw = client.post(f"/api/v1/admin/users/{uid}/reset-password", json={}, headers=h).json()["temporary_password"]
        assert client.post("/api/v1/auth/login", json={"email": email, "password": "secret12"}).status_code == 401
        assert client.post("/api/v1/auth/login", json={"email": email, "password": pw}).status_code == 200


class TestGuardrails:
    def test_admin_cannot_demote_or_deactivate_self(self, client):
        email = _email("self")
        h = _h(register(client, email, role="admin"))
        me = next(u for u in client.get(f"/api/v1/admin/users?q={email}", headers=h).json())
        assert client.patch(f"/api/v1/admin/users/{me['id']}", json={"role": "manager"}, headers=h).status_code == 400
        assert client.patch(f"/api/v1/admin/users/{me['id']}", json={"is_active": False}, headers=h).status_code == 400

    def test_last_admin_cannot_be_removed(self, db_session):
        from app.services.user_service import UserError, user_service

        for u in db_session.exec(select(User).where(User.role == "admin")):
            u.is_active = False
            db_session.add(u)
        db_session.commit()
        sole = User(email=_email("sole"), hashed_password="x", role="admin")
        other = User(email=_email("other"), hashed_password="x", role="manager")
        db_session.add(sole)
        db_session.add(other)
        db_session.commit()
        try:
            user_service.update(db_session, other, sole, {"role": "employee"})
            raised = False
        except UserError:
            raised = True
        assert raised
        for u in db_session.exec(select(User).where(User.role == "admin")):
            u.is_active = True  # restore for other tests
            db_session.add(u)
        db_session.commit()


class TestCsvImport:
    def test_import_creates_skips_and_reports(self, client):
        h = _admin(client)
        existing = _email("exists")
        client.post("/api/v1/admin/users", json={"email": existing}, headers=h)
        good, bad = _email("csv"), _email("csvbad")
        csv_text = (
            "email,full_name,role,department,year,semester,division,password\n"
            f"{good},CSV Student,student,CE,1,2,A,\n"
            f"{existing},Dup,student,CE,,,,\n"
            f"{bad},Bad Dept,student,Nowhere,,,,\n"
        )
        res = client.post("/api/v1/admin/users/import", files={"file": ("users.csv", csv_text.encode(), "text/csv")},
                          headers=h)
        body = res.json()
        assert [c["email"] for c in body["created"]] == [good] and body["created"][0]["temporary_password"]
        assert body["skipped"] == [existing]
        assert body["errors"][0]["line"] == 4 and "department" in body["errors"][0]["error"].lower()

    def test_csv_needs_email_header(self, client):
        res = client.post("/api/v1/admin/users/import", files={"file": ("u.csv", b"name\nx\n", "text/csv")},
                          headers=_admin(client))
        assert res.status_code == 400


class TestSeedDoesNotRevert:
    def test_seed_keeps_admin_changes(self, db_session):
        from app.core.institution_config import InstitutionConfig, InstitutionMember
        from unittest.mock import patch

        from app.services.institution_seed import seed_institution

        email = _email("seed")
        cfg = InstitutionConfig(members=[InstitutionMember(name="Seeded", email=email, role="student", password="p")])
        with patch("app.services.institution_seed.get_institution_config", return_value=cfg):
            seed_institution(db_session)
            user = db_session.exec(select(User).where(User.email == email)).first()
            user.role = "employee"  # an admin promoted them
            db_session.add(user)
            db_session.commit()
            seed_institution(db_session)
        db_session.refresh(user)
        assert user.role == "employee"
