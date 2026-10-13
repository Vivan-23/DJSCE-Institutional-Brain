"""Migrations must reproduce the models exactly: a model change without a migration fails here."""
from alembic import command
from alembic.autogenerate import compare_metadata
from alembic.migration import MigrationContext
from sqlalchemy import create_engine, inspect
from sqlmodel import SQLModel

import app.models.structured  # noqa: F401


def _cfg(conn):
    from app.core.db import _alembic_config

    cfg = _alembic_config()
    cfg.attributes["connection"] = conn
    return cfg


def test_upgrade_matches_models(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'm.db'}")
    with engine.begin() as conn:
        command.upgrade(_cfg(conn), "head")
    with engine.connect() as conn:
        diff = compare_metadata(MigrationContext.configure(conn), SQLModel.metadata)
    assert diff == [], f"Models changed without a migration (run: alembic revision --autogenerate): {diff}"


def test_existing_pre_migration_database_is_stamped_not_recreated(tmp_path):
    from unittest.mock import patch

    from app.core import db as db_mod

    engine = create_engine(f"sqlite:///{tmp_path / 'legacy.db'}")
    SQLModel.metadata.create_all(engine)  # a database created before migrations existed
    with engine.begin() as conn:
        conn.exec_driver_sql("INSERT INTO user (id, email, role, hashed_password, is_active, created_at) "
                             "VALUES ('00000000000000000000000000000001', 'keep@test.com', 'student', 'x', 1, '2026-01-01')")
    with patch.object(db_mod, "engine", engine):
        db_mod.init_db()
        db_mod.init_db()  # idempotent
    with engine.connect() as conn:
        assert inspect(conn).has_table("alembic_version")
        assert conn.exec_driver_sql("SELECT count(*) FROM user").scalar() == 1  # data kept
