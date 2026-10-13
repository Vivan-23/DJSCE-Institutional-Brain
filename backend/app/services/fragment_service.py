"""
Fragment service — the shared evidence layer.

Everything ingested (transcript utterances, uploaded-document chunks, check-in
turns, follow-up replies, connector items) becomes a Fragment: persisted in Postgres and, when
embeddings are available, indexed in ChromaDB for clustering and retrieval.
"""
from datetime import datetime
from typing import Optional
from uuid import UUID, uuid4

import structlog
from sqlmodel import Session, select

# Import modules (not the singletons) so test mocks that patch the module
# attributes (app.services.embedding.embedding_service, app.core.chroma_db.chroma_conn)
# take effect for this service too.
from app.services import embedding as embedding_mod
from app.core import chroma_db as chroma_mod
from app.core.institution_config import ALL_DEPARTMENTS
from app.models.structured import Fragment

log = structlog.get_logger()

#: "internal" evidence is staff-only; "public" evidence is also retrievable by students.
VISIBILITIES = {"internal", "public"}


class FragmentService:
    def create_fragment(
        self,
        db: Session,
        *,
        source_type: str,
        content: str,
        source_ref: Optional[str] = None,
        author_employee_id: Optional[UUID] = None,
        meeting_id: Optional[UUID] = None,
        occurred_at: Optional[datetime] = None,
        visibility: str = "internal",
        speaker: Optional[str] = None,
        department: str = ALL_DEPARTMENTS,
    ) -> Fragment:
        """Persist a fragment and best-effort index its embedding in ChromaDB."""
        if visibility not in VISIBILITIES:
            raise ValueError(f"Invalid visibility '{visibility}'. Allowed: {sorted(VISIBILITIES)}")
        embedding_id = self._index_embedding(
            content,
            metadata={
                "source_type": source_type,
                "source_ref": source_ref or "",
                "visibility": visibility,
                "department": department,  # retrieval scope, filtered in the vector query
                "speaker": speaker or "",  # who said it (transcripts), for provenance in answers
            },
        )
        fragment = Fragment(
            source_type=source_type,
            source_ref=source_ref,
            author_employee_id=author_employee_id,
            meeting_id=meeting_id,
            content=content,
            occurred_at=occurred_at,
            embedding_id=embedding_id,
            visibility=visibility,
            department=department,
        )
        db.add(fragment)
        db.commit()
        db.refresh(fragment)
        return fragment

    def _index_embedding(self, content: str, metadata: dict) -> Optional[str]:
        emb_service = embedding_mod.embedding_service
        chroma_conn = chroma_mod.chroma_conn
        if not getattr(emb_service, "is_available", False) or not getattr(chroma_conn, "collection", None):
            return None
        try:
            vector = emb_service.embed_texts([content])[0]
            embedding_id = str(uuid4())
            chroma_conn.collection.add(
                ids=[embedding_id],
                embeddings=[vector],
                documents=[content],
                metadatas=[metadata],
            )
            return embedding_id
        except Exception as e:
            log.warning("Fragment embedding/index failed", error=str(e))
            return None

    def recent(self, db: Session, *, limit: int = 200) -> list[Fragment]:
        return list(
            db.exec(select(Fragment).order_by(Fragment.created_at.desc()).limit(limit))
        )

    def for_employee(self, db: Session, employee_id: UUID, *, limit: int = 50) -> list[Fragment]:
        return list(
            db.exec(
                select(Fragment)
                .where(Fragment.author_employee_id == employee_id)
                .order_by(Fragment.created_at.desc())
                .limit(limit)
            )
        )


fragment_service = FragmentService()
