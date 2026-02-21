"""
Jan-Seva AI — Embedding Client
Uses sentence-transformers (all-MiniLM-L6-v2) for free, local embedding generation.
384-dimensional vectors for pgvector storage.
"""

from sentence_transformers import SentenceTransformer
import numpy as np


class EmbeddingClient:
    """
    Local embedding generator using sentence-transformers.
    Model: all-MiniLM-L6-v2 (384 dimensions, ~80MB, very fast on CPU).
    """

    def __init__(self, model_name: str = "all-MiniLM-L6-v2"):
        print(f"📦 Loading embedding model: {model_name}...")
        self._model = SentenceTransformer(model_name)
        self._dimension = 384
        print(f"✅ Embedding model loaded. Dimension: {self._dimension}")

    @property
    def dimension(self) -> int:
        """Returns the embedding dimension (384 for MiniLM)."""
        return self._dimension

    def embed_text(self, text: str) -> list[float]:
        """Generate embedding for a single text string."""
        embedding = self._model.encode(text, normalize_embeddings=True)
        return embedding.tolist()

    def embed_batch(self, texts: list[str], batch_size: int = 32) -> list[list[float]]:
        """Generate embeddings for multiple texts efficiently."""
        embeddings = self._model.encode(
            texts,
            batch_size=batch_size,
            normalize_embeddings=True,
            show_progress_bar=True,
        )
        return embeddings.tolist()

    def similarity(self, embedding_a: list[float], embedding_b: list[float]) -> float:
        """Compute cosine similarity between two embeddings."""
        a = np.array(embedding_a)
        b = np.array(embedding_b)
        return float(np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b)))


# --- Singleton ---
_embedding_client: EmbeddingClient | None = None


def get_embedding_client() -> EmbeddingClient:
    """Returns a cached embedding client instance."""
    global _embedding_client
    if _embedding_client is None:
        _embedding_client = EmbeddingClient()
    return _embedding_client
