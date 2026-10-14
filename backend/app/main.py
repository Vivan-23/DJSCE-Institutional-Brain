from contextlib import asynccontextmanager
import structlog
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings
from app.core.db import engine, init_db, startup_lock
from app.api.router import api_router

log = structlog.get_logger()


@asynccontextmanager
async def lifespan(app: FastAPI):
    from sqlmodel import Session
    from app.services.institution_seed import seed_institution

    # One worker at a time: create tables, then seed people from institution.yaml (idempotent).
    with startup_lock():
        init_db()
        with Session(engine) as session:
            seed_institution(session)
            try:  # approved procedures from before they were searchable get their copy once
                from app.services.procedure_service import procedure_service

                procedure_service.publish_missing(session)
            except Exception as e:  # noqa: BLE001 - never block startup on indexing
                log.warning("Publishing approved procedures failed", error=str(e))
    yield


app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.VERSION,
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_origin_regex=r"^https://.*\.ngrok(-free)?\.(dev|app|io)$",
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type"],
)

app.include_router(api_router, prefix="/api/v1")


@app.get("/health")
def health():
    return {"status": "ok", "version": settings.VERSION}
