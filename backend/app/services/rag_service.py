"""
Retrieval-augmented Q&A over indexed institutional knowledge.

Retrieval is filtered by Fragment visibility *inside the vector query*: students
(``public_only=True``) can only ever retrieve ``public`` evidence, so internal
committee transcripts never reach their prompt. Every answer returns the excerpts
it was grounded in, keeping retrieved evidence separate from the model's wording.
"""
from typing import Any, Optional

import structlog

# Import modules (not singletons) so test patches of the module attributes apply.
from app.core import chroma_db as chroma_mod
from app.core import neo4j_db as neo4j_mod
from app.core.institution_config import get_institution_config
from app.services import embedding as embedding_mod
from app.services.llm_service import llm_service

log = structlog.get_logger()

_TOP_K = 5
_EXCERPT_CHARS = 500
_PROCEDURE_CHARS = 1500  # an approved procedure is cited whole (steps + rules)
_PROCEDURE_K = 2


class RAGService:
    def retrieve(
        self, question: str, *, public_only: bool, departments: Optional[list[str]] = None, k: int = _TOP_K
    ) -> list[dict[str, Any]]:
        """Top-k evidence excerpts for ``question``, restricted to public evidence if asked and
        to ``departments`` (codes, incl. "all") when given; None means every department."""
        emb = embedding_mod.embedding_service
        collection = getattr(chroma_mod.chroma_conn, "collection", None)
        if not collection or not getattr(emb, "is_available", False):
            return []
        try:
            vector = emb.embed_texts([question])[0]
            clauses: list[dict] = []
            if public_only:
                clauses.append({"visibility": "public"})
            if departments is not None:
                clauses.append({"department": {"$in": list(departments)}})
            where: Optional[dict] = (
                None if not clauses else clauses[0] if len(clauses) == 1 else {"$and": clauses}
            )
            # Approved procedures are searched on their own so a reviewed SOP can lead the context.
            proc_where = {"$and": clauses + [{"source_type": "procedure"}]} if clauses else {"source_type": "procedure"}
            try:
                proc = collection.query(query_embeddings=[vector], n_results=_PROCEDURE_K, where=proc_where)
            except Exception:  # noqa: BLE001 - no procedures indexed yet, or an older store
                proc = {}
            res = collection.query(query_embeddings=[vector], n_results=k, where=where)
        except Exception as e:
            log.warning("Vector retrieval failed", error=str(e))
            return []

        docs = (res.get("documents") or [[]])[0]
        metas = (res.get("metadatas") or [[]])[0] or [{}] * len(docs)
        dists = (res.get("distances") or [[]])[0]
        # A procedure leads only if it is at least as close as the third-best ordinary hit.
        bar = sorted(dists)[min(2, len(dists) - 1)] if dists else None
        lead_docs, lead_metas = [], []
        if bar is not None and isinstance(proc, dict):
            for d, m, dist in zip((proc.get("documents") or [[]])[0], (proc.get("metadatas") or [[]])[0] or [],
                                  (proc.get("distances") or [[]])[0]):
                if dist is not None and dist <= bar:
                    lead_docs.append(d)
                    lead_metas.append(m)
        sources, seen = [], set()
        for doc, meta in zip(lead_docs + list(docs), lead_metas + list(metas)):
            meta = meta or {}
            if not doc or doc in seen:
                continue
            if public_only and meta.get("visibility") != "public":
                continue  # defence in depth: never trust the store's filter alone
            if departments is not None and meta.get("department") not in departments:
                continue
            if len(sources) >= k + _PROCEDURE_K:
                break
            seen.add(doc)
            is_procedure = meta.get("source_type") == "procedure"
            sources.append(
                {
                    "ref": len(sources) + 1,
                    "source_type": meta.get("source_type") or None,
                    "source_ref": meta.get("source_ref") or None,
                    "visibility": meta.get("visibility") or "internal",
                    "department": meta.get("department") or None,
                    "source_url": meta.get("source_url") or None,
                    "speaker": meta.get("speaker") or None,
                    "skill_id": meta.get("skill_id") or None,
                    "excerpt": doc[:_PROCEDURE_CHARS if is_procedure else _EXCERPT_CHARS],
                }
            )
        return sources

    def _graph_context(self) -> str:
        try:
            rows = neo4j_mod.neo4j_conn.execute_query(
                "MATCH (n) RETURN n.name AS name, labels(n)[0] AS type LIMIT 15"
            )
            entities = [f"{r['name']} ({r['type']})" for r in rows if r.get("name")]
            return ("Known entities in the institutional graph: " + ", ".join(entities)) if entities else ""
        except Exception as e:
            log.warning("Graph context fetch failed", error=str(e))
            return ""

    def answer(
        self,
        question: str,
        *,
        public_only: bool,
        departments: Optional[list[str]] = None,
        purpose: str = "answer",
    ) -> dict[str, Any]:
        """Return ``{"answer": str, "sources": [...]}`` grounded in retrieved evidence.

        ``purpose="ticket_draft"`` writes a reply for a staff member to review and send,
        marking gaps in [brackets] instead of telling the reader to raise a ticket.
        """
        sources = self.retrieve(question, public_only=public_only, departments=departments)
        if not llm_service.is_available:
            return {"answer": "The language model is not configured (set GROQ_API_KEY).", "sources": sources}

        audience = "a student" if public_only else "a faculty or staff member"
        # Label each excerpt with where it came from (meeting title / document name) so the
        # model can connect "the Academic Council meeting" to an utterance that never names it.
        context = "\n\n".join(
            f"[{s['ref']}] ({s.get('source_type') or 'source'}: {s.get('source_ref') or 'untitled'}"
            + (f"; speaker: {s['speaker']}" if s.get("speaker") else "")
            + f") {s['excerpt']}"
            for s in sources
        ) or "(no matching documents)"
        graph = "" if public_only else self._graph_context()
        if purpose == "ticket_draft":
            task = (
                f"You draft help-desk replies for {get_institution_config().name}. A faculty member "
                "will review and edit your draft before it is sent to the person who raised the "
                "ticket. Use ONLY the numbered context below and cite it inline like [1]. Where the "
                "context lacks something needed, write a short holding reply and mark each missing "
                "fact as [TO CONFIRM: ...] for staff. Never invent policy, dates, or names, and do "
                "not quote internal deliberations verbatim. Items labelled 'Approved procedure' are the "
                "institution's reviewed procedure: follow them over anything said in meetings.\n\n"
            )
        else:
            task = (
                f"You are the {get_institution_config().name} assistant, answering {audience}. "
                "Answer using ONLY the numbered context below and cite it inline like [1]. Each "
                "item states where it came from (meeting title or document name). If the context "
                "does not contain the answer, say so plainly and suggest raising a help-desk "
                "ticket — never guess or invent policy, dates, or names. Items labelled 'Approved procedure' "
                "are the institution's reviewed procedure: prefer them over meeting discussion and say so.\n\n"
            )
        system = (
            task
            + f"--- Context ---\n{context}"
            + (f"\n\n--- Institutional Graph ---\n{graph}" if graph else "")
        )
        text = llm_service.complete(system, question, max_tokens=1024, temperature=0.2)
        return {"answer": text, "sources": sources}


rag_service = RAGService()
