from contextlib import contextmanager
from pathlib import Path

from sqlalchemy import inspect, text
from sqlmodel import create_engine, Session
from app.core.config import settings

engine = create_engine(
    settings.DATABASE_URL,
    pool_pre_ping=True,   # detect stale connections
    pool_size=5,
    max_overflow=10,
)


_BACKEND_DIR = Path(__file__).resolve().parents[2]  # backend/ (holds alembic.ini + migrations/)


def _alembic_config():
    from alembic.config import Config

    cfg = Config(str(_BACKEND_DIR / "alembic.ini"))
    cfg.set_main_option("script_location", str(_BACKEND_DIR / "migrations"))
    return cfg


def init_db() -> None:
    """Bring the schema up to date with Alembic migrations, keeping existing data.

    A database created before migrations existed (tables present, no ``alembic_version``)
    is stamped at the baseline instead of being re-created.
    """
    # Import all table models so they register on SQLModel.metadata (migrations/env.py uses it).
    from app.models.structured import (  # noqa: F401
        User, Document, ProgressReport, ActiveInsight,
        Employee, Meeting, Fragment, Commitment, CommitmentUpdate,
        CheckIn, Skill, SkillCitation, AuditLog, Ticket, QueryLog, Notice, NoticeRecipient,
    )
    from alembic import command

    cfg = _alembic_config()
    with engine.begin() as conn:
        cfg.attributes["connection"] = conn
        tables = inspect(conn)
        if tables.has_table("user") and not tables.has_table("alembic_version"):
            command.stamp(cfg, "head")
        else:
            command.upgrade(cfg, "head")


# Arbitrary app-wide key for the Postgres advisory lock that serializes startup.
_STARTUP_LOCK_KEY = 724_001


@contextmanager
def startup_lock():
    """Serialize schema creation + seeding across processes.

    The API runs several uvicorn workers (plus Celery). On a fresh database they would
    all CREATE TABLE / seed users at once and crash on duplicate-key races. A
    session-level Postgres advisory lock makes them take turns; it is a no-op on SQLite.
    """
    if engine.dialect.name != "postgresql":
        yield
        return
    with engine.connect() as conn:
        conn.execute(text("SELECT pg_advisory_lock(:k)"), {"k": _STARTUP_LOCK_KEY})
        try:
            yield
        finally:
            conn.execute(text("SELECT pg_advisory_unlock(:k)"), {"k": _STARTUP_LOCK_KEY})


def get_session():
    with Session(engine) as session:
        yield session
