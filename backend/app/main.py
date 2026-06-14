from contextlib import asynccontextmanager
import structlog
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings
from app.core.db import engine, init_db
from app.api.router import api_router

log = structlog.get_logger()


def _seed_demo_user() -> None:
    """Create a demo user on first startup if the users table is empty."""
    from sqlmodel import Session, select
    from app.models.structured import User
    from app.api.v1.auth import hash_password

    with Session(engine) as session:
        if session.exec(select(User)).first():
            return
        user = User(
            email="demo@companybrain.ai",
            full_name="Demo User",
            hashed_password=hash_password("demo123"),
            role="admin",
        )
        session.add(user)
        session.commit()
        log.info("Demo user seeded", email="demo@companybrain.ai", password="demo123")


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    _seed_demo_user()
    yield


app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.VERSION,
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type"],
)

app.include_router(api_router, prefix="/api/v1")


@app.get("/health")
def health():
    return {"status": "ok", "version": settings.VERSION}
