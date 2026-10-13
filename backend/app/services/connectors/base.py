"""
Source connector framework (FR1).

The Institutional Brain ingests from many fragmented sources — Slack, email, tickets,
docs, databases — not just manual uploads. Every connector normalizes its
source into the shared evidence unit (``Fragment``) so the rest of the pipeline
(clustering, extraction, freshness) is source-agnostic.

Live provider integrations (real Slack/Gmail/Zendesk tokens) are out of V1
scope; the concrete connectors here are credential-aware stubs that degrade to a
no-op when unconfigured and accept pushed items so the pipeline is exercisable
end-to-end today.
"""
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional

import structlog
from sqlmodel import Session

from app.services.audit_service import audit_service
from app.services.employee_service import employee_service
from app.services.fragment_service import fragment_service

log = structlog.get_logger()


@dataclass
class RawFragment:
    """A normalized item fetched from a source, before it becomes a Fragment."""
    content: str
    author: Optional[str] = None  # display name; resolved to an Employee on sync
    source_ref: Optional[str] = None  # permalink / external id (for citation + freshness)
    occurred_at: Optional[datetime] = None
    metadata: dict = field(default_factory=dict)


class BaseConnector(ABC):
    #: stable identifier used in the API and as the Fragment.source_type
    name: str = "base"
    #: human-facing label
    label: str = "Base Connector"

    @property
    def is_configured(self) -> bool:
        """Whether live credentials are present. Stubs override; default False."""
        return False

    @abstractmethod
    def fetch(self) -> list[RawFragment]:
        """Pull new items from the source. Return [] when unconfigured."""
        raise NotImplementedError

    def sync(self, db: Session, items: Optional[list[RawFragment]] = None) -> int:
        """Persist fetched (or supplied) items as Fragments. Returns the count stored."""
        items = items if items is not None else self.fetch()
        stored = 0
        for item in items:
            content = (item.content or "").strip()
            if not content:
                continue
            author_id = None
            if item.author:
                emp = employee_service.resolve_or_create(db, item.author)
                author_id = emp.id if emp else None
            fragment_service.create_fragment(
                db,
                source_type=self.name,
                content=content,
                source_ref=item.source_ref,
                author_employee_id=author_id,
                occurred_at=item.occurred_at,
            )
            stored += 1
        if stored:
            audit_service.record(
                db, actor=f"connector:{self.name}", action="source_sync",
                metadata={"stored": stored},
            )
        log.info("Connector sync complete", connector=self.name, stored=stored)
        return stored
