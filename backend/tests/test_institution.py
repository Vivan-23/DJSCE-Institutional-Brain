"""Tests for the institution profile: config loader, branding API, and member seeding."""
import textwrap

from sqlmodel import select

from app.core.institution_config import InstitutionConfig, get_institution_config
from app.models.structured import Employee, User
from app.services.institution_seed import seed_institution


class TestInstitutionConfigLoader:
    def test_parses_custom_profile(self, tmp_path, monkeypatch):
        profile = tmp_path / "institution.yaml"
        profile.write_text(
            textwrap.dedent(
                """
                institution:
                  name: "Test Institute Brain"
                  short_code: "TIB"
                  email_domain: "tib.test"
                settings:
                  pa_checkin_hour: 18
                  commitment_followup_hours: 24
                helpdesk:
                  categories:
                    - key: "Exams"
                      label: "Examinations"
                      routed_to: "Exam Cell"
                      keywords: [Exam, Result]
                      quick_questions: ["When are results out?"]
                members:
                  - name: "Dana Lee"
                    email: "Dana@TIB.test"
                    role: "admin"
                    password: "pw123456"
                  - name: "Ravi Patel"
                    email: "ravi@tib.test"
                    role: "manager"
                    manager: "dana@tib.test"
                    department: "Computer Engineering"
                  - name: "Stu Dent"
                    email: "stu@tib.test"
                    role: "student"
                  - name: "Bad Role"
                    email: "bad@tib.test"
                    role: "superuser"
                """
            ),
            encoding="utf-8",
        )
        monkeypatch.setenv("INSTITUTION_CONFIG", str(profile))
        get_institution_config.cache_clear()
        try:
            cfg = get_institution_config()
            assert cfg.name == "Test Institute Brain"
            assert cfg.short_code == "TIB"
            assert cfg.pa_checkin_hour == 18
            assert cfg.commitment_followup_hours == 24
            assert [m.email for m in cfg.members] == ["dana@tib.test", "ravi@tib.test", "stu@tib.test"]
            assert cfg.members[1].manager == "dana@tib.test"
            assert cfg.members[1].department == "Computer Engineering"
            assert cfg.members[2].role == "student"
            exams = cfg.helpdesk_categories[0]
            assert exams.key == "exams" and exams.routed_to == "Exam Cell"
            assert exams.keywords == ["exam", "result"]  # normalized lowercase
        finally:
            get_institution_config.cache_clear()

    def test_missing_file_falls_back_to_defaults(self, tmp_path, monkeypatch):
        monkeypatch.setenv("INSTITUTION_CONFIG", str(tmp_path / "does_not_exist.yaml"))
        get_institution_config.cache_clear()
        try:
            cfg = get_institution_config()
            assert isinstance(cfg, InstitutionConfig)
            assert cfg.name and cfg.short_code
        finally:
            get_institution_config.cache_clear()


class TestBrandingAPI:
    def test_institution_endpoint_is_public(self, client):
        res = client.get("/api/v1/institution")  # no auth header
        assert res.status_code == 200
        body = res.json()
        assert {"name", "short_code", "full_name"} <= body.keys()


class TestInstitutionSeeding:
    def test_seed_is_idempotent_and_students_are_not_staff(self, db_session, monkeypatch, tmp_path):
        profile = tmp_path / "institution.yaml"
        profile.write_text(
            textwrap.dedent(
                """
                institution: { name: "Seed Institute", short_code: "SI" }
                members:
                  - name: "Boss Person"
                    email: "boss@seed.test"
                    role: "admin"
                    password: "pw123456"
                    timezone: "Asia/Kolkata"
                  - name: "Report Person"
                    email: "report@seed.test"
                    role: "employee"
                    manager: "boss@seed.test"
                  - name: "Student Person"
                    email: "student@seed.test"
                    role: "student"
                    password: "pw123456"
                """
            ),
            encoding="utf-8",
        )
        monkeypatch.setenv("INSTITUTION_CONFIG", str(profile))
        get_institution_config.cache_clear()
        try:
            first = seed_institution(db_session)
            second = seed_institution(db_session)

            assert first["employees_created"] == 2  # the student is not a staff Employee
            assert first["users_created"] == 2
            assert second["employees_created"] == 0
            assert second["users_created"] == 0

            student = db_session.exec(select(User).where(User.email == "student@seed.test")).first()
            assert student is not None and student.role == "student"
            assert db_session.exec(select(Employee).where(Employee.user_id == student.id)).first() is None

            emps = {e.display_name: e for e in db_session.exec(select(Employee))}
            assert emps["Report Person"].manager_id == emps["Boss Person"].id
            assert emps["Boss Person"].timezone == "Asia/Kolkata"
        finally:
            get_institution_config.cache_clear()
