"""PostGIS spatial query engine for detection geospatial lookups."""

from typing import List

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker


class SpatialQueryEngine:
    """Executes PostGIS spatial queries against the detections table."""

    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self.session_factory = session_factory

    async def get_detections_in_radius(
        self,
        lat: float,
        lon: float,
        radius_m: float,
        limit: int = 100,
    ) -> List[dict]:
        """Return detections within *radius_m* metres of a point."""
        query = text("""
            SELECT
                d.detection_id::text,
                d.detection_type,
                d.confidence_score,
                d.bounding_box,
                d.caption,
                ST_Y(d.location::geometry) AS lat,
                ST_X(d.location::geometry) AS lon,
                ST_Distance(
                    d.location::geography,
                    ST_SetSRID(ST_MakePoint(:lon, :lat), 4326)::geography
                ) AS distance_m
            FROM detections d
            WHERE d.location IS NOT NULL
              AND ST_DWithin(
                    d.location::geography,
                    ST_SetSRID(ST_MakePoint(:lon, :lat), 4326)::geography,
                    :radius
                  )
            ORDER BY distance_m ASC
            LIMIT :limit
        """)
        async with self.session_factory() as session:
            result = await session.execute(
                query,
                {"lat": lat, "lon": lon, "radius": radius_m, "limit": limit},
            )
            return [dict(row._mapping) for row in result.fetchall()]

    async def get_detections_in_bbox(
        self,
        min_lon: float,
        min_lat: float,
        max_lon: float,
        max_lat: float,
        limit: int = 500,
    ) -> List[dict]:
        """Return detections inside a bounding box."""
        query = text("""
            SELECT
                d.detection_id::text,
                d.detection_type,
                d.confidence_score,
                d.bounding_box,
                d.caption,
                ST_Y(d.location::geometry) AS lat,
                ST_X(d.location::geometry) AS lon
            FROM detections d
            WHERE d.location IS NOT NULL
              AND ST_Intersects(
                    d.location::geometry,
                    ST_MakeEnvelope(:min_lon, :min_lat, :max_lon, :max_lat, 4326)
                  )
            ORDER BY d.created_at DESC
            LIMIT :limit
        """)
        async with self.session_factory() as session:
            result = await session.execute(
                query,
                {
                    "min_lon": min_lon,
                    "min_lat": min_lat,
                    "max_lon": max_lon,
                    "max_lat": max_lat,
                    "limit": limit,
                },
            )
            return [dict(row._mapping) for row in result.fetchall()]

    async def get_detections_in_barangay(self, barangay_name: str) -> List[dict]:
        """Return all detections whose location falls inside the named barangay polygon."""
        query = text("""
            SELECT
                d.detection_id::text,
                d.detection_type,
                d.confidence_score,
                d.bounding_box,
                d.caption,
                ST_Y(d.location::geometry) AS lat,
                ST_X(d.location::geometry) AS lon
            FROM detections d
            JOIN locations l ON ST_Contains(l.geometry, d.location::geometry)
            WHERE d.location IS NOT NULL
              AND l.barangay_name = :barangay_name
            ORDER BY d.created_at DESC
        """)
        async with self.session_factory() as session:
            result = await session.execute(query, {"barangay_name": barangay_name})
            return [dict(row._mapping) for row in result.fetchall()]

    async def calculate_distance(
        self, lat1: float, lon1: float, lat2: float, lon2: float
    ) -> float:
        """Return geodesic distance in metres between two points using PostGIS."""
        query = text("""
            SELECT ST_Distance(
                ST_SetSRID(ST_MakePoint(:lon1, :lat1), 4326)::geography,
                ST_SetSRID(ST_MakePoint(:lon2, :lat2), 4326)::geography
            ) AS distance_m
        """)
        async with self.session_factory() as session:
            result = await session.execute(
                query,
                {"lat1": lat1, "lon1": lon1, "lat2": lat2, "lon2": lon2},
            )
            return float(result.scalar())

    async def get_nearest_detections(
        self, lat: float, lon: float, limit: int = 10
    ) -> List[dict]:
        """Return the *limit* closest detections to a point, ordered by distance."""
        query = text("""
            SELECT
                d.detection_id::text,
                d.detection_type,
                d.confidence_score,
                d.bounding_box,
                d.caption,
                ST_Y(d.location::geometry) AS lat,
                ST_X(d.location::geometry) AS lon,
                ST_Distance(
                    d.location::geography,
                    ST_SetSRID(ST_MakePoint(:lon, :lat), 4326)::geography
                ) AS distance_m
            FROM detections d
            WHERE d.location IS NOT NULL
            ORDER BY d.location::geometry <-> ST_SetSRID(ST_MakePoint(:lon, :lat), 4326)
            LIMIT :limit
        """)
        async with self.session_factory() as session:
            result = await session.execute(
                query, {"lat": lat, "lon": lon, "limit": limit}
            )
            return [dict(row._mapping) for row in result.fetchall()]
