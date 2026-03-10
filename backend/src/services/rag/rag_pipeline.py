"""End-to-end RAG pipeline: query -> embed -> retrieve -> generate."""

from __future__ import annotations

import logging
import re
from typing import Dict, List, Optional

from src.services.rag.ollama_client import OllamaClient
from src.services.rag.embedder import EmbeddingService
from src.services.rag.vector_store import VectorStoreService
from src.services.rag.prompts import SYSTEM_PROMPT, QUERY_TEMPLATE, build_context

logger = logging.getLogger(__name__)

_FALLBACK_ANSWER = (
    "I'm sorry, the AI language model is currently unavailable. "
    "Based on the retrieved detections, please review the data below "
    "for relevant infrastructure information."
)


class RAGPipeline:
    """Orchestrates retrieval-augmented generation for walkability queries."""

    def __init__(
        self,
        ollama_client: OllamaClient,
        embedding_service: EmbeddingService,
        vector_store: VectorStoreService,
    ) -> None:
        self.ollama = ollama_client
        self.embedder = embedding_service
        self.vector_store = vector_store

    async def answer_query(
        self,
        query: str,
        filters: Optional[Dict] = None,
    ) -> dict:
        """Full RAG flow: rewrite -> embed -> retrieve -> generate.

        Returns
        -------
        dict with keys: answer, citations, sources
        """
        # Step 1 - Query rewriting
        rewritten = self._rewrite_query(query)

        # Step 2 - Embed the query
        query_embedding = self.embedder.embed_text(rewritten)

        # Step 3 - Retrieve relevant detections
        filters = filters or {}
        if "lat" in filters and "lon" in filters:
            detections = await self.vector_store.hybrid_search(
                query_embedding=query_embedding,
                lat=filters["lat"],
                lon=filters["lon"],
                radius_m=filters.get("radius_m", 1000.0),
                limit=filters.get("limit", 10),
            )
        else:
            detections = await self.vector_store.similarity_search(
                query_embedding=query_embedding,
                limit=filters.get("limit", 10),
            )

        # Step 4 - Build context
        context_str = self._build_context(detections)

        # Step 5 - Generate answer with LLM (with fallback)
        prompt = QUERY_TEMPLATE.format(
            system=SYSTEM_PROMPT,
            context=context_str,
            query=rewritten,
        )

        try:
            answer = self.ollama.generate(
                prompt=prompt,
                temperature=0.3,
                max_tokens=500,
            )
        except Exception as exc:
            logger.warning("Ollama generation failed, using fallback: %s", exc)
            answer = _FALLBACK_ANSWER
            if detections:
                answer += "\n\n" + context_str

        # Step 6 - Extract citations
        citations = self._extract_citations(answer, detections)

        return {
            "answer": answer,
            "citations": citations,
            "sources": [
                {
                    "detection_id": str(d.get("detection_id", "")),
                    "detection_type": d.get("detection_type", ""),
                    "confidence_score": d.get("confidence_score", 0.0),
                    "caption": d.get("caption", ""),
                }
                for d in detections
            ],
        }

    def _rewrite_query(self, query: str) -> str:
        """Expand abbreviations and add domain context to the query."""
        rewrites = {
            r"\bpwd\b": "persons with disability accessibility",
            r"\bada\b": "accessibility compliance",
            r"\bsidewalk\b": "sidewalk pedestrian walkway",
            r"\bpothole\b": "pothole road surface damage",
            r"\bramp\b": "curb ramp wheelchair accessibility",
        }
        rewritten = query
        for pattern, replacement in rewrites.items():
            rewritten = re.sub(pattern, replacement, rewritten, flags=re.IGNORECASE)
        return rewritten

    def _build_context(self, detections: List[dict]) -> str:
        """Delegate to the prompts module."""
        return build_context(detections)

    def _extract_citations(
        self,
        response: str,
        detections: List[dict],
    ) -> List[str]:
        """Pull bracketed citation numbers from the LLM response."""
        # Match patterns like [1], [2], etc.
        refs = re.findall(r"\[(\d+)\]", response)
        cited_indices = set()
        for ref in refs:
            idx = int(ref) - 1  # 1-based to 0-based
            if 0 <= idx < len(detections):
                cited_indices.add(idx)

        citations = []
        for idx in sorted(cited_indices):
            det = detections[idx]
            citations.append(
                f"[{idx + 1}] {det.get('detection_type', 'unknown')} "
                f"at ({det.get('lat', 'N/A')}, {det.get('lon', 'N/A')}) "
                f"- confidence {det.get('confidence_score', 0):.0%}"
            )

        return citations
