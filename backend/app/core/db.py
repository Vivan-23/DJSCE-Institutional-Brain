from sqlmodel import create_engine, Session, SQLModel
from app.core.config import settings

engine = create_engine(
    settings.DATABASE_URL,
    pool_pre_ping=True,   # detect stale connections
    pool_size=5,
    max_overflow=10,
)


def init_db() -> None:
    # Import all table models so they register on SQLModel.metadata before create_all
    from app.models.structured import (  # noqa: F401
        User, Document, ProgressReport, ActiveInsight,
        Employee, Meeting, Fragment, Commitment, CommitmentUpdate,
        CheckIn, Skill, SkillCitation, AuditLog,
    )
    SQLModel.metadata.create_all(engine)


def get_session():
    with Session(engine) as session:
        yield session
