"""Sentence-level embedding and similarity utilities for captions."""

from __future__ import annotations

import logging
import threading
from typing import Any, List, Optional

import numpy as np

logger = logging.getLogger(__name__)


class CaptionEmbedder:
    """Embeds captions into dense vectors using a sentence-transformer model.

    The default model (``all-MiniLM-L6-v2``) produces **384-dimensional**
    vectors suitable for cosine-similarity search.

    Parameters:
        model_name: Hugging Face model identifier.
    """

    EMBEDDING_DIM = 384

    def __init__(
        self,
        model_name: str = "sentence-transformers/all-MiniLM-L6-v2",
    ) -> None:
        self.model_name = model_name
        self._model: Any | None = None
        self._lock = threading.Lock()

        logger.info("CaptionEmbedder configured: model_name=%s", self.model_name)

    # ------------------------------------------------------------------
    # Model loading
    # ------------------------------------------------------------------

    def _load_model(self) -> Any:
        """Lazily load the SentenceTransformer model (thread-safe)."""
        if self._model is None:
            with self._lock:
                if self._model is None:
                    from sentence_transformers import SentenceTransformer

                    logger.info(
                        "Loading sentence-transformer model: %s", self.model_name
                    )
                    self._model = SentenceTransformer(self.model_name)
                    logger.info("Sentence-transformer model loaded successfully")
        return self._model

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def embed_caption(self, caption: str) -> List[float]:
        """Produce a 384-dimensional embedding for a single caption.

        Args:
            caption: Plain text caption string.

        Returns:
            List of floats with length ``EMBEDDING_DIM``.
        """
        model = self._load_model()
        embedding: np.ndarray = model.encode(caption, convert_to_numpy=True)
        return embedding.tolist()

    def embed_captions_batch(self, captions: List[str]) -> List[List[float]]:
        """Produce embeddings for multiple captions in one call.

        Args:
            captions: List of caption strings.

        Returns:
            List of embedding vectors (each of length ``EMBEDDING_DIM``).
        """
        model = self._load_model()
        embeddings: np.ndarray = model.encode(captions, convert_to_numpy=True)
        return [vec.tolist() for vec in embeddings]

    def compute_similarity(self, caption1: str, caption2: str) -> float:
        """Compute cosine similarity between two captions.

        Returns:
            A float in ``[-1, 1]``; ``1.0`` means identical direction.
        """
        vec1 = np.array(self.embed_caption(caption1))
        vec2 = np.array(self.embed_caption(caption2))

        dot = float(np.dot(vec1, vec2))
        norm1 = float(np.linalg.norm(vec1))
        norm2 = float(np.linalg.norm(vec2))

        if norm1 == 0.0 or norm2 == 0.0:
            return 0.0

        return dot / (norm1 * norm2)
