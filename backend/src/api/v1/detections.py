"""Detection query endpoints: list, nearby radius search, heatmap."""

from __future__ import annotations

from datetime import datetime
from typing import List, Optional

from fastapi import APIRouter, Query
from pydantic import BaseModel, ConfigDict

router = APIRouter(prefix="/api/v1/detections", tags=["detections"])


# ── Response Models ──────────────────────────────────────────────────────────


class DetectionItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    detection_id: str
    image_id: str
    detection_type: str
    confidence_score: float
    bounding_box: dict
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    caption: Optional[str] = None
    created_at: datetime


class DetectionListResponse(BaseModel):
    detections: List[DetectionItem]
    total: int
    limit: int
    offset: int


class HeatmapPoint(BaseModel):
    latitude: float
    longitude: float
    weight: float


class HeatmapResponse(BaseModel):
    points: List[HeatmapPoint]
    total: int


# ── Endpoints ────────────────────────────────────────────────────────────────


@router.get("/", response_model=DetectionListResponse)
async def list_detections(
    type: Optional[str] = Query(None, description="Filter by detection type"),
    confidence_min: float = Query(0.0, ge=0.0, le=1.0, description="Minimum confidence"),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
):
    """List detections with optional filters."""
    # TODO: query database with filters
    return DetectionListResponse(detections=[], total=0, limit=limit, offset=offset)


@router.get("/nearby", response_model=DetectionListResponse)
async def nearby_detections(
    lat: float = Query(..., description="Latitude"),
    lon: float = Query(..., description="Longitude"),
    radius_m: float = Query(500.0, ge=1, le=5000, description="Search radius in metres"),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
):
    """Find detections within *radius_m* of a point."""
    # TODO: PostGIS ST_DWithin query
    return DetectionListResponse(detections=[], total=0, limit=limit, offset=offset)


@router.get("/heatmap", response_model=HeatmapResponse)
async def heatmap(
    min_lat: float = Query(...),
    min_lon: float = Query(...),
    max_lat: float = Query(...),
    max_lon: float = Query(...),
):
    """Return heatmap-ready weighted points for the given viewport bounding box."""
    # TODO: aggregate detections in viewport using DBSCAN clustering
    return HeatmapResponse(points=[], total=0)
