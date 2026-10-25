from fastapi import APIRouter
from app.api.v1 import (
    auth, ingest, insights, chat, graph, transcripts, commitments, pa, skills,
    sources, audit, institution, helpdesk, calendar, analytics, admin, notices, schedule, timetables, assistant,
)

api_router = APIRouter()
api_router.include_router(auth.router, prefix="/auth", tags=["auth"])
api_router.include_router(ingest.router, prefix="/ingest", tags=["ingest"])
api_router.include_router(insights.router, prefix="/insights", tags=["insights"])
api_router.include_router(chat.router, prefix="/chat", tags=["chat"])
api_router.include_router(assistant.router, prefix="/assistant", tags=["assistant"])
api_router.include_router(graph.router, prefix="/graph", tags=["graph"])
api_router.include_router(transcripts.router, prefix="/transcripts", tags=["transcripts"])
api_router.include_router(commitments.router, prefix="/commitments", tags=["commitments"])
api_router.include_router(pa.router, prefix="/pa", tags=["pa"])
api_router.include_router(skills.router, prefix="/skills", tags=["skills"])
api_router.include_router(sources.router, prefix="/sources", tags=["sources"])
api_router.include_router(audit.router, prefix="/audit", tags=["audit"])
api_router.include_router(institution.router, prefix="/institution", tags=["institution"])
api_router.include_router(helpdesk.router, prefix="/helpdesk", tags=["helpdesk"])
api_router.include_router(calendar.router, prefix="/calendar", tags=["calendar"])
api_router.include_router(analytics.router, prefix="/analytics", tags=["analytics"])
api_router.include_router(admin.router, prefix="/admin", tags=["admin"])
api_router.include_router(notices.router, prefix="/notices", tags=["notices"])
api_router.include_router(schedule.router, prefix="/schedule", tags=["schedule"])
api_router.include_router(timetables.router, prefix="/timetables", tags=["timetables"])
