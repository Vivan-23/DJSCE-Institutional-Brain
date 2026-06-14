import structlog
from typing import List

log = structlog.get_logger()

_EMBEDDING_DIM = 1024  # BGE-large-en-v1.5 output dimension


class EmbeddingService:
    def __init__(self, model_name: str = "BAAI/bge-large-en-v1.5") -> None:
        self.model = None
        self.model_name = model_name
        try:
            from sentence_transformers import SentenceTransformer
            self.model = SentenceTransformer(model_name)
            log.info("Embedding model loaded", model=model_name)
        except Exception as e:
            log.error(
                "Failed to load embedding model — embeddings disabled",
                model=model_name,
                error=str(e),
            )

    @property
    def is_available(self) -> bool:
        return self.model is not None

    def embed_texts(self, texts: List[str]) -> List[List[float]]:
        if not self.model:
            raise RuntimeError(
                f"Embedding model '{self.model_name}' is not available. "
                "Check logs for the load error."
            )
        return self.model.encode(texts, normalize_embeddings=True).tolist()


embedding_service = EmbeddingService()
