"""Per-barangay detection statistics and rankings."""

from typing import List

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker


class BarangayStatsCalculator:
    """Compute detection statistics scoped to barangay polygons."""

    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self.session_factory = session_factory

    async def calculate_stats(self, barangay_name: str) -> dict:
        """Return aggregate stats for a single barangay.

        Keys: barangay_name, total_detections, by_type, avg_confidence, area_km2.
        """
        query = text("""
            SELECT
                l.barangay_name,
                COUNT(d.detection_id) AS total_detections,
                AVG(d.confidence_score) AS avg_confidence,
                ST_Area(l.geometry::geography) / 1e6 AS area_km2
            FROM locations l
            LEFT JOIN detections d
                ON d.location IS NOT NULL
               AND ST_Contains(l.geometry, d.location::geometry)
            WHERE l.barangay_name = :barangay_name
            GROUP BY l.barangay_name, l.geometry
        """)

        by_type_query = text("""
            SELECT
                d.detection_type,
                COUNT(*) AS cnt
            FROM detections d
            JOIN locations l
                ON ST_Contains(l.geometry, d.location::geometry)
            WHERE l.barangay_name = :barangay_name
              AND d.location IS NOT NULL
            GROUP BY d.detection_type
        """)

        async with self.session_factory() as session:
            result = await session.execute(query, {"barangay_name": barangay_name})
            row = result.fetchone()

            if row is None:
                return {
                    "barangay_name": barangay_name,
                    "total_detections": 0,
                    "by_type": {},
                    "avg_confidence": None,
                    "area_km2": None,
                }

            mapping = row._mapping
            total_detections = int(mapping["total_detections"])
            avg_confidence = (
                round(float(mapping["avg_confidence"]), 4)
                if mapping["avg_confidence"] is not None
                else None
            )
            area_km2 = (
                round(float(mapping["area_km2"]), 4)
                if mapping["area_km2"] is not None
                else None
            )

            type_result = await session.execute(
                by_type_query, {"barangay_name": barangay_name}
            )
            by_type = {
                row_t._mapping["detection_type"]: int(row_t._mapping["cnt"])
                for row_t in type_result.fetchall()
            }

        return {
            "barangay_name": barangay_name,
            "total_detections": total_detections,
            "by_type": by_type,
            "avg_confidence": avg_confidence,
            "area_km2": area_km2,
        }

    async def get_all_rankings(self) -> List[dict]:
        """Return all barangays ranked by detection density (detections per km2)."""
        query = text("""
            SELECT
                l.barangay_name,
                COUNT(d.detection_id) AS total_detections,
                AVG(d.confidence_score) AS avg_confidence,
                ST_Area(l.geometry::geography) / 1e6 AS area_km2
            FROM locations l
            LEFT JOIN detections d
                ON d.location IS NOT NULL
               AND ST_Contains(l.geometry, d.location::geometry)
            WHERE l.geometry IS NOT NULL
            GROUP BY l.barangay_name, l.geometry
            ORDER BY
                CASE
                    WHEN ST_Area(l.geometry::geography) > 0
                    THEN COUNT(d.detection_id) / (ST_Area(l.geometry::geography) / 1e6)
                    ELSE 0
                END DESC
        """)

        async with self.session_factory() as session:
            result = await session.execute(query)
            rows = result.fetchall()

        rankings: List[dict] = []
        for row in rows:
            m = row._mapping
            total = int(m["total_detections"])
            area = (
                round(float(m["area_km2"]), 4)
                if m["area_km2"] is not None
                else None
            )
            density = round(total / area, 4) if area and area > 0 else 0.0
            rankings.append(
                {
                    "barangay_name": m["barangay_name"],
                    "total_detections": total,
                    "avg_confidence": (
                        round(float(m["avg_confidence"]), 4)
                        if m["avg_confidence"] is not None
                        else None
                    ),
                    "area_km2": area,
                    "density_per_km2": density,
                }
            )

        return rankings
