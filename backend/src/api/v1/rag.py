"""RAG (Retrieval-Augmented Generation) query endpoint."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel

router = APIRouter(prefix="/api/v1/rag", tags=["rag"])


# ── Request / Response Models ────────────────────────────────────────────────


class RAGQueryRequest(BaseModel):
    query: str
    filters: Optional[Dict[str, Any]] = None


class RAGSource(BaseModel):
    detection_id: str
    detection_type: str
    confidence_score: float
    caption: str


class RAGQueryResponse(BaseModel):
    answer: str
    citations: List[str]
    sources: List[RAGSource]


# ── Endpoint ─────────────────────────────────────────────────────────────────


@router.post("/query", response_model=RAGQueryResponse)
async def rag_query(body: RAGQueryRequest):
    """Answer a walkability question using RAG.

    TODO: wire up RAGPipeline once dependency injection is in place.
    """
    if not body.query.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Query must not be empty",
        )

    # Placeholder until RAGPipeline is wired
    return RAGQueryResponse(
        answer="RAG pipeline is not yet connected. Please try again later.",
        citations=[],
        sources=[],
    )
