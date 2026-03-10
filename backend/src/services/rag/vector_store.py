"""Vector store backed by pgvector + PostGIS."""

from __future__ import annotations

import logging
from typing import List
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

logger = logging.getLogger(__name__)


class VectorStoreService:
    """Pgvector-backed similarity search with optional spatial filtering."""

    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self.session_factory = session_factory

    async def add_detection_embedding(
        self,
        detection_id: UUID,
        embedding: List[float],
    ) -> None:
        """Store or update an embedding for a detection row."""
        async with self.session_factory() as session:
            await session.execute(
                text(
                    "UPDATE detections SET embedding = :embedding "
                    "WHERE detection_id = :detection_id"
                ),
                {
                    "detection_id": str(detection_id),
                    "embedding": str(embedding),
                },
            )
            await session.commit()

    async def similarity_search(
        self,
        query_embedding: List[float],
        limit: int = 10,
    ) -> List[dict]:
        """Pure vector similarity search using pgvector cosine distance."""
        async with self.session_factory() as session:
            result = await session.execute(
                text(
                    """
                    SELECT
                        d.detection_id,
                        d.detection_type,
                        d.confidence_score,
                        d.caption,
                        d.created_at,
                        ST_X(d.location::geometry) AS lon,
                        ST_Y(d.location::geometry) AS lat,
                        d.embedding <=> :query_embedding AS distance
                    FROM detections d
                    WHERE d.embedding IS NOT NULL
                    ORDER BY d.embedding <=> :query_embedding
                    LIMIT :limit
                    """
                ),
                {
                    "query_embedding": str(query_embedding),
                    "limit": limit,
                },
            )
            rows = result.mappings().all()
            return [dict(r) for r in rows]

    async def hybrid_search(
        self,
        query_embedding: List[float],
        lat: float,
        lon: float,
        radius_m: float,
        limit: int = 10,
    ) -> List[dict]:
        """Combine vector similarity with spatial proximity (ST_DWithin)."""
        async with self.session_factory() as session:
            result = await session.execute(
                text(
                    """
                    SELECT
                        d.detection_id,
                        d.detection_type,
                        d.confidence_score,
                        d.caption,
                        d.created_at,
                        ST_X(d.location::geometry) AS lon,
                        ST_Y(d.location::geometry) AS lat,
                        d.embedding <=> :query_embedding AS distance
                    FROM detections d
                    WHERE d.embedding IS NOT NULL
                      AND ST_DWithin(
                            d.location::geography,
                            ST_SetSRID(ST_MakePoint(:lon, :lat), 4326)::geography,
                            :radius_m
                          )
                    ORDER BY d.embedding <=> :query_embedding
                    LIMIT :limit
                    """
                ),
                {
                    "query_embedding": str(query_embedding),
                    "lat": lat,
                    "lon": lon,
                    "radius_m": radius_m,
                    "limit": limit,
                },
            )
            rows = result.mappings().all()
            return [dict(r) for r in rows]
