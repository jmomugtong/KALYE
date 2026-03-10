"""Text embedding service using sentence-transformers."""

from __future__ import annotations

import logging
from typing import List

from sentence_transformers import SentenceTransformer

logger = logging.getLogger(__name__)


class EmbeddingService:
    """Produces 384-dimensional embeddings with all-MiniLM-L6-v2."""

    def __init__(self, model_name: str = "all-MiniLM-L6-v2") -> None:
        self.model_name = model_name
        self._model: SentenceTransformer | None = None

    @property
    def model(self) -> SentenceTransformer:
        if self._model is None:
            logger.info("Loading embedding model: %s", self.model_name)
            self._model = SentenceTransformer(self.model_name)
        return self._model

    def embed_text(self, text: str) -> List[float]:
        """Embed a single text string into a 384-dim vector."""
        embedding = self.model.encode(text, convert_to_numpy=True)
        return embedding.tolist()

    def embed_batch(self, texts: List[str]) -> List[List[float]]:
        """Embed a batch of texts."""
        embeddings = self.model.encode(texts, convert_to_numpy=True)
        return [e.tolist() for e in embeddings]

    def embed_detection(
        self,
        detection_type: str,
        location: str,
        confidence: float,
        caption: str,
    ) -> List[float]:
        """Create an embedding from structured detection metadata.

        Combines the detection fields into a descriptive sentence
        before encoding.
        """
        text = (
            f"{detection_type} detected at {location} "
            f"with {confidence:.0%} confidence. {caption}"
        )
        return self.embed_text(text)
