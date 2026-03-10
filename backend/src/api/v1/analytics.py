"""Analytics endpoints: walkability scores, rankings, trends."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException, Query, status
from pydantic import BaseModel

router = APIRouter(prefix="/api/v1/analytics", tags=["analytics"])


# ── Response Models ──────────────────────────────────────────────────────────


class WalkabilityResponse(BaseModel):
    score: int
    breakdown: Dict[str, Any]
    location_id: str
    calculated_at: str
    version: str


class RankingEntry(BaseModel):
    location_id: str
    barangay_name: str
    city: str
    score: int


class RankingsResponse(BaseModel):
    rankings: List[RankingEntry]
    order: str


class TrendPoint(BaseModel):
    week_start: str
    week_end: str
    score: float
    sample_count: int


class TrendResponse(BaseModel):
    location_id: str
    weeks: int
    trend: List[TrendPoint]


# ── Endpoints ────────────────────────────────────────────────────────────────


@router.get("/walkability/{barangay_name}", response_model=WalkabilityResponse)
async def get_walkability(barangay_name: str):
    """Return the walkability score for a barangay.

    TODO: wire up WalkabilityCalculator once DB dependency injection is in place.
    """
    raise HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail=f"Barangay '{barangay_name}' not found",
    )


@router.get("/walkability/rankings", response_model=RankingsResponse)
async def get_rankings(
    order: str = Query("desc", pattern="^(asc|desc)$"),
    limit: int = Query(10, ge=1, le=100),
):
    """Top or bottom barangays by walkability score."""
    # TODO: query latest scores joined with locations, ordered
    return RankingsResponse(rankings=[], order=order)


@router.get("/trends", response_model=TrendResponse)
async def get_trends(
    location_id: str = Query(..., description="Location UUID"),
    weeks: int = Query(12, ge=1, le=52),
):
    """Weekly walkability trend for a location."""
    # TODO: wire up TrendAnalyzer
    return TrendResponse(location_id=location_id, weeks=weeks, trend=[])
