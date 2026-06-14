import json
import structlog
from app.core.config import settings
from app.core.chroma_db import chroma_conn
from app.services.embedding import embedding_service
from app.core.neo4j_db import neo4j_conn

log = structlog.get_logger()


class RAGService:
    def __init__(self) -> None:
        self.client = None
        if settings.GROQ_API_KEY:
            try:
                import groq
                self.client = groq.Groq(api_key=settings.GROQ_API_KEY)
                log.info("Groq client initialized")
            except Exception as e:
                log.error("Failed to initialize Groq client", error=str(e))

    def query(self, user_query: str) -> str:
        if not self.client:
            return "LLM not configured. Please set GROQ_API_KEY in your .env file."

        # 1. Embed query
        try:
            query_embedding = embedding_service.embed_texts([user_query])[0]
        except RuntimeError as e:
            log.warning("Embedding unavailable for query", error=str(e))
            query_embedding = None

        # 2. ChromaDB similarity search (top-5)
        context_chunks: list[str] = []
        if query_embedding and chroma_conn.collection:
            try:
                results = chroma_conn.collection.query(
                    query_embeddings=[query_embedding],
                    n_results=5,
                )
                if results and results["documents"]:
                    context_chunks = results["documents"][0]
            except Exception as e:
                log.warning("ChromaDB query failed", error=str(e))

        # 3. Graph context (known entities)
        graph_context = ""
        try:
            res = neo4j_conn.execute_query(
                "MATCH (n) RETURN n.name AS name, labels(n)[0] AS type LIMIT 15"
            )
            entities = [
                f"{r['name']} ({r['type']})" for r in res if r.get("name")
            ]
            if entities:
                graph_context = "Known entities in the org graph: " + ", ".join(entities)
        except Exception as e:
            log.warning("Graph context fetch failed", error=str(e))

        system_prompt = (
            "You are Company Brain, an organizational intelligence assistant. "
            "Answer the user's question using ONLY the context provided below. "
            "If the answer is not in the context, say so clearly — do not guess.\n\n"
            "--- Context Documents ---\n"
            + "\n\n".join(f"[{i+1}] {c}" for i, c in enumerate(context_chunks))
            + ("\n\n--- Org Graph ---\n" + graph_context if graph_context else "")
        )

        try:
            completion = self.client.chat.completions.create(
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_query},
                ],
                model="meta-llama/llama-4-scout-17b-16e-instruct",
                max_tokens=1024,
                temperature=0.2,
            )
            return completion.choices[0].message.content
        except Exception as e:
            log.error("Groq API call failed", error=str(e))
            raise


rag_service = RAGService()
