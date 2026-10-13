import structlog
from celery import Celery
from celery.schedules import crontab

from app.core.config import settings

log = structlog.get_logger()

celery_app = Celery(
    "djsce_brain",
    broker=settings.REDIS_URL,
    backend=settings.REDIS_URL,
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    beat_schedule={
        # Daily organizational intelligence sweep
        "daily-active-intelligence": {
            "task": "app.core.celery.run_daily_active_intelligence",
            "schedule": crontab(hour=8, minute=0),
        },
        # Prepare each employee's end-of-day check-in
        "daily-pa-checkins": {
            "task": "app.core.celery.run_daily_checkins",
            "schedule": crontab(hour=settings.PA_CHECKIN_HOUR, minute=0),
        },
        # Nudge owners of stale/overdue commitments (hourly eligibility scan)
        "commitment-followups": {
            "task": "app.core.celery.run_commitment_followups",
            "schedule": crontab(minute=0),
        },
        # Procedure extraction + freshness scan over accumulated fragments
        "skill-extraction": {
            "task": "app.core.celery.run_skill_extraction",
            "schedule": crontab(hour=3, minute=0),
        },
        "freshness-scan": {
            "task": "app.core.celery.run_freshness_scan",
            "schedule": crontab(hour=4, minute=0),
        },
    },
)


@celery_app.task(name="app.core.celery.process_document")
def process_document_task(text: str, filename: str, visibility: str = "internal") -> dict:
    """
    Background ingestion pipeline:
      1. Persist a Document row to Postgres
      2. Chunk the text; each chunk becomes a Fragment (Postgres + Chroma index)
         carrying the document's visibility, so documents feed retrieval,
         procedure extraction and citations exactly like transcripts do
      3. Extract named entities with spaCy → upsert to Neo4j
    """
    from app.services.parser import chunk_document
    from app.services.fragment_service import fragment_service
    from app.services.ner_service import ner_service
    from app.services.graph_service import graph_service
    from app.core.db import engine
    from app.models.structured import Document
    from sqlmodel import Session

    log.info("Starting document processing", filename=filename, visibility=visibility)

    # --- 1 + 2. Document row, then chunk → Fragments ---
    chunks = chunk_document(text)
    with Session(engine) as session:
        session.add(Document(title=filename, source_type="upload", raw_content=text[:5_000]))
        session.commit()
        for chunk in chunks:
            fragment_service.create_fragment(
                session,
                source_type="document",
                source_ref=filename,
                content=chunk,
                visibility=visibility,
            )
    log.info("Document chunks stored as fragments", filename=filename, count=len(chunks))

    # --- 3. NER → Neo4j: one Document node with MENTIONS edges ---
    from app.services.graph_service import graph_entities

    entities = ner_service.extract_entities(text)
    people, bodies = graph_entities(text, entities)
    try:
        graph_service.record_document(filename, visibility, people, bodies)
    except Exception as e:
        log.warning("Graph write failed", filename=filename, error=str(e))
    log.info("Entities linked in graph", filename=filename, people=len(people), bodies=len(bodies))

    return {
        "filename": filename,
        "chunks_stored": len(chunks),
        "visibility": visibility,
        "persons_found": [p["name"] for p in people],
        "orgs_found": bodies,
    }


@celery_app.task(name="app.core.celery.process_transcript")
def process_transcript_task(transcript: str, title: str, source: str = "upload") -> dict:
    """
    Background transcript pipeline:
      1. LLM extraction → summary, decisions, commitments
      2. Persist Meeting + speaker-attributed Fragments
      3. Create Commitments (resolving assignees to Employees)
    """
    from app.core.db import engine
    from app.services.transcript_service import transcript_service
    from sqlmodel import Session

    log.info("Starting transcript processing", title=title)
    with Session(engine) as session:
        result = transcript_service.ingest(
            session, transcript=transcript, title=title, source=source
        )
    log.info("Transcript processing complete", title=title, **{
        "commitments": result.get("commitments_created"),
        "fragments": result.get("fragments"),
    })

    # Meeting → graph: participants ATTENDED it; bodies it discussed are MENTIONED.
    from app.services.graph_service import graph_entities, graph_service
    from app.services.ner_service import ner_service

    try:
        people, bodies = graph_entities(
            transcript, ner_service.extract_entities(transcript), known_people=result.get("speakers") or []
        )
        graph_service.record_meeting(title, people, bodies)
    except Exception as e:
        log.warning("Meeting graph write failed", title=title, error=str(e))
    return result


@celery_app.task(name="app.core.celery.run_daily_active_intelligence")
def run_daily_active_intelligence() -> str:
    from app.core.db import engine
    from app.services.active_intel import active_intel_service
    from sqlmodel import Session

    with Session(engine) as session:
        count = active_intel_service.check_bottlenecks(session)

    log.info("Daily intelligence run complete", insights_created=count)
    return f"Created {count} insights"


@celery_app.task(name="app.core.celery.run_daily_checkins")
def run_daily_checkins() -> str:
    """Pre-create today's end-of-day check-in for each active employee."""
    from app.core.db import engine
    from app.services.employee_service import employee_service
    from app.services.pa_service import pa_service
    from sqlmodel import Session

    prepared = 0
    with Session(engine) as session:
        for emp in employee_service.list_active(session):
            pa_service.get_today_checkin(session, emp)
            prepared += 1
    log.info("Daily check-ins prepared", count=prepared)
    return f"Prepared {prepared} check-ins"


@celery_app.task(name="app.core.celery.run_commitment_followups")
def run_commitment_followups() -> str:
    """Scan for stale commitments and record a follow-up nudge per owner."""
    from app.core.db import engine
    from app.services.employee_service import employee_service
    from app.services.pa_service import pa_service
    from app.services.audit_service import audit_service
    from sqlmodel import Session

    generated = 0
    with Session(engine) as session:
        for emp in employee_service.list_active(session):
            followups = pa_service.pending_followups(session, emp)
            for f in followups:
                audit_service.record(
                    session,
                    actor="pa",
                    action="followup_generated",
                    target_id=f["commitment_id"],
                    metadata={"employee": emp.display_name},
                )
            generated += len(followups)
    log.info("Commitment follow-ups generated", count=generated)
    return f"Generated {generated} follow-ups"


@celery_app.task(name="app.core.celery.run_skill_extraction")
def run_skill_extraction() -> str:
    """Cluster accumulated fragments and synthesize candidate skills for review."""
    from app.core.db import engine
    from app.services.skill_service import skill_service
    from sqlmodel import Session

    with Session(engine) as session:
        created = skill_service.extract_candidates(session)
    log.info("Skill extraction complete", candidates=created)
    return f"Created {created} candidate skills"


@celery_app.task(name="app.core.celery.run_freshness_scan")
def run_freshness_scan() -> str:
    """Compare recent evidence against approved skills; flag contradictions stale."""
    from app.core.db import engine
    from app.services.freshness_service import freshness_service
    from sqlmodel import Session

    with Session(engine) as session:
        flagged = freshness_service.scan(session)
    log.info("Freshness scan complete", flagged=flagged)
    return f"Flagged {flagged} skills stale"
