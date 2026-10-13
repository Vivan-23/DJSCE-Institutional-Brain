"""
Coordinator analytics: commitments per committee, help-desk resolution, most-asked questions.

Everything is computed on read from existing tables (Commitment/Meeting, Ticket,
QueryLog, Fragment, Skill); there is no analytics store to keep in sync.
"""
import re
from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone
from statistics import median
from typing import Any, Optional

from sqlmodel import Session, select

from app.models.structured import Commitment, Fragment, Meeting, QueryLog, Skill, Ticket
from app.services.ticket_service import ticket_service

_OPEN = {"open", "in_progress", "blocked"}


def _aware(dt: datetime) -> datetime:
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


def _norm_question(q: str) -> str:
    """Group trivially different phrasings: lowercase, strip punctuation and spaces."""
    return re.sub(r"\s+", " ", re.sub(r"[^\w\s]", " ", q.lower())).strip()


class AnalyticsService:
    def commitments_by_meeting(self, db: Session, now: datetime) -> list[dict[str, Any]]:
        meetings = {m.id: m for m in db.exec(select(Meeting))}
        rows: dict[str, dict[str, Any]] = {}
        for c in db.exec(select(Commitment)):
            m = meetings.get(c.source_meeting_id)
            key = m.title if m else "Not linked to a meeting"
            row = rows.setdefault(key, {
                "meeting": key, "department": m.department if m else "all",
                "open": 0, "done": 0, "dropped": 0, "overdue": 0, "total": 0,
            })
            row["total"] += 1
            if c.status in _OPEN:
                row["open"] += 1
                if c.due_date and _aware(c.due_date) < now:
                    row["overdue"] += 1
            elif c.status in ("done", "dropped"):
                row[c.status] += 1
        return sorted(rows.values(), key=lambda r: (-r["open"], r["meeting"]))

    def tickets(self, db: Session, now: datetime) -> dict[str, Any]:
        tickets = list(db.exec(select(Ticket)))
        hours = [
            (_aware(t.replied_at) - _aware(t.created_at)).total_seconds() / 3600
            for t in tickets if t.replied_at
        ]
        by_category: dict[str, Counter] = defaultdict(Counter)
        for t in tickets:
            by_category[t.category][t.status] += 1
        stale = [t for t in tickets if t.status == "open" and now - _aware(t.created_at) > timedelta(hours=48)]
        return {
            "total": len(tickets),
            "by_status": dict(Counter(t.status for t in tickets)),
            "by_category": [
                {"category": cat, **dict(counts), "total": sum(counts.values())}
                for cat, counts in sorted(by_category.items(), key=lambda kv: -sum(kv[1].values()))
            ],
            "triage_method": dict(Counter(t.triage_method for t in tickets)),
            "resolution_hours": {
                "n": len(hours),
                "median": round(median(hours), 1) if hours else None,
                "mean": round(sum(hours) / len(hours), 1) if hours else None,
            },
            "open_over_48h": len(stale),
        }

    def questions(self, db: Session, now: datetime, days: int) -> dict[str, Any]:
        since = now - timedelta(days=days)
        logs = [q for q in db.exec(select(QueryLog)) if _aware(q.created_at) >= since]
        groups: dict[str, dict[str, Any]] = {}
        for q in logs:
            g = groups.setdefault(_norm_question(q.question), {"question": q.question, "count": 0, "no_sources": 0})
            g["count"] += 1
            g["no_sources"] += q.source_count == 0
        top = sorted(groups.values(), key=lambda g: (-g["count"], g["question"]))[:10]
        gaps = sorted((g for g in groups.values() if g["no_sources"]), key=lambda g: -g["no_sources"])[:10]
        # Topic = the help-desk category the offline keyword classifier assigns (no LLM calls).
        topics = Counter(ticket_service.keyword_triage(q.question)["category"] for q in logs)
        return {
            "days": days,
            "total": len(logs),
            "by_role": dict(Counter(q.role for q in logs)),
            "by_topic": dict(topics.most_common()),
            "top": top,
            "knowledge_gaps": gaps,
        }

    def knowledge(self, db: Session) -> dict[str, Any]:
        frags = list(db.exec(select(Fragment)))
        return {
            "fragments": len(frags),
            "by_visibility": dict(Counter(f.visibility for f in frags)),
            "by_department": dict(Counter(f.department for f in frags).most_common()),
            "procedures_by_status": dict(Counter(s.status for s in db.exec(select(Skill)))),
        }

    def summary(self, db: Session, *, days: int = 30, now: Optional[datetime] = None) -> dict[str, Any]:
        now = now or datetime.now(timezone.utc)
        return {
            "generated_at": now.isoformat(),
            "commitments_by_meeting": self.commitments_by_meeting(db, now),
            "tickets": self.tickets(db, now),
            "questions": self.questions(db, now, days),
            "knowledge": self.knowledge(db),
        }


analytics_service = AnalyticsService()
