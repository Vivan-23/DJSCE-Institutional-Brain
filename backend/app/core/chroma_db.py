import structlog
import chromadb
from app.core.config import settings

log = structlog.get_logger()


class ChromaConnection:
    def __init__(self) -> None:
        self.client = None
        self.collection = None
        try:
            self.client = chromadb.HttpClient(
                host=settings.CHROMA_HOST,
                port=settings.CHROMA_PORT,
            )
            self.collection = self.client.get_or_create_collection(
                name="djsce_knowledge",
                metadata={"hnsw:space": "cosine"},
            )
            log.info("ChromaDB connected", host=settings.CHROMA_HOST, port=settings.CHROMA_PORT)
        except Exception as e:
            log.error("ChromaDB connection failed — vector search will be unavailable", error=str(e))


chroma_conn = ChromaConnection()
