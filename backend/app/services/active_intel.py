import structlog
from sqlmodel import Session

from app.core.neo4j_db import neo4j_conn
from app.models.structured import ActiveInsight

log = structlog.get_logger()


class ActiveIntelService:
    def check_bottlenecks(self, db: Session) -> int:
        """
        Detect employees assigned to more than 3 projects and create risk insights.
        Returns the number of insights created.
        """
        query = """
        MATCH (e:Employee)-[:WORKS_ON]->(p:Project)
        WITH e, count(p) AS activeProjects
        WHERE activeProjects > 3
        RETURN e.name AS name, e.email AS email, activeProjects
        """
        created = 0
        try:
            results = neo4j_conn.execute_query(query)
            for r in results:
                label = r.get("name") or r.get("email", "Unknown")
                insight = ActiveInsight(
                    category="risk",
                    observation=f"{label} is assigned to {r['activeProjects']} active projects.",
                    impact_rationale="Overloaded team members are a leading indicator of missed deadlines and quality issues.",
                    suggested_actions='["Reassign lower-priority tasks", "Adjust sprint deadlines", "Discuss capacity with the team"]',
                    confidence_score=0.85,
                )
                db.add(insight)
                created += 1
            db.commit()
            if created:
                log.info("Bottleneck insights created", count=created)
        except Exception as e:
            log.error("Bottleneck check failed", error=str(e))
            db.rollback()
        return created

    def check_stalled_projects(self, db: Session) -> int:
        """
        Detect projects with no recent activity (no WORKS_ON edges populated yet).
        Placeholder for future timeline-aware analysis.
        """
        return 0


active_intel_service = ActiveIntelService()
