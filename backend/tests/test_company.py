"""Tests for the company profile: config loader, branding API, and org seeding."""
import textwrap

from sqlmodel import select

from app.core.company_config import CompanyConfig, get_company_config
from app.models.structured import Employee, User
from app.services.company_seed import seed_company


class TestCompanyConfigLoader:
    def test_parses_custom_profile(self, tmp_path, monkeypatch):
        profile = tmp_path / "company.yaml"
        profile.write_text(
            textwrap.dedent(
                """
                company:
                  name: "Acme Corp"
                  short_code: "AC"
                  email_domain: "acme.com"
                settings:
                  pa_checkin_hour: 18
                  commitment_followup_hours: 24
                employees:
                  - name: "Dana Lee"
                    email: "Dana@Acme.com"
                    role: "admin"
                    password: "pw123456"
                  - name: "Ravi Patel"
                    email: "ravi@acme.com"
                    role: "manager"
                    manager: "dana@acme.com"
                    timezone: "America/New_York"
                """
            ),
            encoding="utf-8",
        )
        monkeypatch.setenv("COMPANY_CONFIG", str(profile))
        get_company_config.cache_clear()
        try:
            cfg = get_company_config()
            assert cfg.name == "Acme Corp"
            assert cfg.short_code == "AC"
            assert cfg.pa_checkin_hour == 18
            assert cfg.commitment_followup_hours == 24
            assert len(cfg.employees) == 2
            assert cfg.employees[0].email == "dana@acme.com"  # normalized lowercase
            assert cfg.employees[1].manager == "dana@acme.com"
        finally:
            get_company_config.cache_clear()  # restore default for other tests

    def test_missing_file_falls_back_to_defaults(self, tmp_path, monkeypatch):
        monkeypatch.setenv("COMPANY_CONFIG", str(tmp_path / "does_not_exist.yaml"))
        get_company_config.cache_clear()
        try:
            # Even with a bogus COMPANY_CONFIG, other candidate paths (repo-root
            # company.yaml) resolve; the result is always a valid CompanyConfig.
            cfg = get_company_config()
            assert isinstance(cfg, CompanyConfig)
            assert cfg.name and cfg.short_code
        finally:
            get_company_config.cache_clear()


class TestBrandingAPI:
    def test_company_endpoint_is_public(self, client):
        res = client.get("/api/v1/company")  # no auth header
        assert res.status_code == 200
        body = res.json()
        assert "name" in body and "short_code" in body


class TestCompanySeeding:
    def test_seed_is_idempotent(self, db_session, monkeypatch, tmp_path):
        profile = tmp_path / "company.yaml"
        profile.write_text(
            textwrap.dedent(
                """
                company: { name: "Seed Co", short_code: "SC" }
                employees:
                  - name: "Boss Person"
                    email: "boss@seedco.test"
                    role: "admin"
                    password: "pw123456"
                    timezone: "Asia/Kolkata"
                  - name: "Report Person"
                    email: "report@seedco.test"
                    role: "employee"
                    manager: "boss@seedco.test"
                """
            ),
            encoding="utf-8",
        )
        monkeypatch.setenv("COMPANY_CONFIG", str(profile))
        get_company_config.cache_clear()
        try:
            first = seed_company(db_session)
            second = seed_company(db_session)

            # First run creates rows; second run is a no-op (idempotent).
            assert first["employees_created"] == 2
            assert second["employees_created"] == 0
            assert second["users_created"] == 0

            boss = db_session.exec(select(User).where(User.email == "boss@seedco.test")).first()
            assert boss is not None and boss.role == "admin"

            report = next(
                e for e in db_session.exec(select(Employee))
                if e.display_name == "Report Person"
            )
            boss_emp = next(
                e for e in db_session.exec(select(Employee))
                if e.display_name == "Boss Person"
            )
            assert report.manager_id == boss_emp.id  # manager link resolved
            assert boss_emp.timezone == "Asia/Kolkata"
        finally:
            get_company_config.cache_clear()
