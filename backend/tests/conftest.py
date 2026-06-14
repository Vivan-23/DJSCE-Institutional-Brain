"""
Test configuration.

Secrets are injected as environment variables BEFORE any app module is imported
so that pydantic-settings can read them. All external services (Postgres, Neo4j,
ChromaDB, Redis, Groq) are mocked — the test suite runs without any Docker
infrastructure.
"""
import os

# Must be set before importing app modules (pydantic-settings reads on class creation)
os.environ.setdefault("GROQ_API_KEY", "test-groq-key")
os.environ.setdefault("SECRET_KEY", "test-secret-key-at-least-32-chars-long-ok")
os.environ.setdefault("NEO4J_PASSWORD", "test-password")
os.environ.setdefault("DATABASE_URL", "sqlite:///./test_company_brain.db")

import pytest
from fastapi.testclient import TestClient
from sqlmodel import SQLModel, create_engine, Session
from unittest.mock import MagicMock, patch

# ── In-memory SQLite engine for tests ─────────────────────────────────────────
TEST_DB_URL = "sqlite:///./test_company_brain.db"


@pytest.fixture(scope="session")
def test_engine():
    engine = create_engine(TEST_DB_URL, connect_args={"check_same_thread": False})
    from app.models.structured import (  # noqa: F401
        User, Document, ProgressReport, ActiveInsight,
        Employee, Meeting, Fragment, Commitment, CommitmentUpdate,
        CheckIn, Skill, SkillCitation, AuditLog,
    )
    SQLModel.metadata.create_all(engine)
    yield engine
    SQLModel.metadata.drop_all(engine)
    # Dispose the connection pool before deleting the file — on Windows an open
    # handle otherwise raises PermissionError (WinError 32) during teardown.
    engine.dispose()
    import os
    try:
        if os.path.exists("test_company_brain.db"):
            os.remove("test_company_brain.db")
    except PermissionError:
        pass


@pytest.fixture()
def db_session(test_engine):
    with Session(test_engine) as session:
        yield session


@pytest.fixture()
def client(test_engine):
    """FastAPI TestClient with mocked external dependencies."""
    mock_chroma = MagicMock()
    mock_chroma.collection = MagicMock()
    mock_chroma.collection.query.return_value = {"documents": [["mock context chunk"]]}

    mock_neo4j = MagicMock()
    mock_neo4j.execute_query.return_value = []

    mock_embedding = MagicMock()
    mock_embedding.is_available = True
    mock_embedding.embed_texts.return_value = [[0.1] * 10]

    mock_groq_client = MagicMock()
    mock_groq_client.chat.completions.create.return_value = MagicMock(
        choices=[MagicMock(message=MagicMock(content="Mock answer from LLM"))]
    )

    with (
        patch("app.core.chroma_db.chroma_conn", mock_chroma),
        patch("app.core.neo4j_db.neo4j_conn", mock_neo4j),
        patch("app.services.embedding.embedding_service", mock_embedding),
        patch("app.services.rag_service.rag_service.client", mock_groq_client),
        patch("app.services.rag_service.embedding_service", mock_embedding),
        patch("app.services.rag_service.chroma_conn", mock_chroma),
        patch("app.services.rag_service.neo4j_conn", mock_neo4j),
    ):
        from app.main import app
        from app.core.db import get_session

        def override_session():
            with Session(test_engine) as session:
                yield session

        app.dependency_overrides[get_session] = override_session

        with TestClient(app, raise_server_exceptions=False) as c:
            yield c

        app.dependency_overrides.clear()
