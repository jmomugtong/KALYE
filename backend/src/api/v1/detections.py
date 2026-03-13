"""Detection query endpoints — wired to PostGIS."""

from __future__ import annotations

from datetime import datetime
from typing import List, Optional

from fastapi import APIRouter, Depends, Query
from geoalchemy2.functions import ST_DWithin, ST_MakePoint, ST_SetSRID, ST_X, ST_Y
from pydantic import BaseModel, ConfigDict
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.db.models import Detection
from src.db.postgres import get_session

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


# ── Helpers ──────────────────────────────────────────────────────────────────


def _row_to_item(row) -> DetectionItem:
    """Convert a query row (Detection + lat/lng columns) into a response item."""
    det = row[0]  # Detection ORM object
    lat = row[1]  # ST_Y result
    lng = row[2]  # ST_X result
    return DetectionItem(
        detection_id=str(det.detection_id),
        image_id=str(det.image_id),
        detection_type=det.detection_type.value,
        confidence_score=det.confidence_score,
        bounding_box=det.bounding_box,
        latitude=lat,
        longitude=lng,
        caption=det.caption,
        created_at=det.created_at,
    )


# ── Endpoints ────────────────────────────────────────────────────────────────


@router.get("/", response_model=DetectionListResponse)
async def list_detections(
    type: Optional[str] = Query(None, description="Filter by detection type"),
    confidence_min: float = Query(0.0, ge=0.0, le=1.0, description="Minimum confidence"),
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    session: AsyncSession = Depends(get_session),
):
    """List detections with optional filters. Public endpoint."""
    stmt = (
        select(
            Detection,
            ST_Y(Detection.location).label("lat"),
            ST_X(Detection.location).label("lng"),
        )
        .where(Detection.location.isnot(None))
        .where(Detection.confidence_score >= confidence_min)
    )

    if type:
        stmt = stmt.where(Detection.detection_type == type)

    # Count total
    count_stmt = select(func.count()).select_from(stmt.subquery())
    total = (await session.execute(count_stmt)).scalar() or 0

    # Fetch page
    stmt = stmt.order_by(Detection.created_at.desc()).limit(limit).offset(offset)
    rows = (await session.execute(stmt)).all()

    return DetectionListResponse(
        detections=[_row_to_item(row) for row in rows],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.get("/nearby", response_model=DetectionListResponse)
async def nearby_detections(
    lat: float = Query(..., description="Latitude"),
    lon: float = Query(..., description="Longitude"),
    radius_m: float = Query(500.0, ge=1, le=5000, description="Search radius in metres"),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    session: AsyncSession = Depends(get_session),
):
    """Find detections within *radius_m* of a point."""
    point = ST_SetSRID(ST_MakePoint(lon, lat), 4326)

    stmt = (
        select(
            Detection,
            ST_Y(Detection.location).label("lat"),
            ST_X(Detection.location).label("lng"),
        )
        .where(Detection.location.isnot(None))
        .where(ST_DWithin(Detection.location, point, radius_m / 111320.0))
    )

    count_stmt = select(func.count()).select_from(stmt.subquery())
    total = (await session.execute(count_stmt)).scalar() or 0

    stmt = stmt.order_by(Detection.created_at.desc()).limit(limit).offset(offset)
    rows = (await session.execute(stmt)).all()

    return DetectionListResponse(
        detections=[_row_to_item(row) for row in rows],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.get("/heatmap", response_model=HeatmapResponse)
async def heatmap(
    min_lat: float = Query(...),
    min_lon: float = Query(...),
    max_lat: float = Query(...),
    max_lon: float = Query(...),
    session: AsyncSession = Depends(get_session),
):
    """Return heatmap-ready weighted points for the given viewport bounding box."""
    from geoalchemy2.functions import ST_Within, ST_MakeEnvelope

    envelope = ST_MakeEnvelope(min_lon, min_lat, max_lon, max_lat, 4326)

    stmt = (
        select(
            ST_Y(Detection.location).label("lat"),
            ST_X(Detection.location).label("lng"),
            Detection.confidence_score,
        )
        .where(Detection.location.isnot(None))
        .where(ST_Within(Detection.location, envelope))
    )

    rows = (await session.execute(stmt)).all()

    points = [HeatmapPoint(latitude=r.lat, longitude=r.lng, weight=r.confidence_score) for r in rows]
    return HeatmapResponse(points=points, total=len(points))
