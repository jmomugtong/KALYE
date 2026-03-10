"""Analyse a pedestrian route for walkability issues."""

from typing import List, Tuple

import numpy as np

from src.geo.spatial_queries import SpatialQueryEngine

# Earth radius in metres
_EARTH_RADIUS_M = 6_371_000


def _haversine(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Return distance in metres between two WGS-84 points."""
    lat1, lon1, lat2, lon2 = map(np.radians, [lat1, lon1, lat2, lon2])
    dlat = lat2 - lat1
    dlon = lon2 - lon1
    a = np.sin(dlat / 2) ** 2 + np.cos(lat1) * np.cos(lat2) * np.sin(dlon / 2) ** 2
    return float(2 * _EARTH_RADIUS_M * np.arcsin(np.sqrt(a)))


class RouteAnalyzer:
    """Evaluate walkability along a polyline route."""

    def __init__(self, spatial_engine: SpatialQueryEngine) -> None:
        self.spatial_engine = spatial_engine

    async def analyze_route(
        self,
        route_coords: List[Tuple[float, float]],
        buffer_m: float = 50,
    ) -> dict:
        """Collect detections along a route and compute summary statistics.

        *route_coords* is a list of ``(lat, lon)`` tuples.

        Returns a dict with:
          - total_distance_m
          - detections (deduplicated list)
          - detection_count
          - issues_per_100m
          - by_type (counts keyed by detection_type)
        """
        if len(route_coords) < 2:
            return {
                "total_distance_m": 0.0,
                "detections": [],
                "detection_count": 0,
                "issues_per_100m": 0.0,
                "by_type": {},
            }

        # Total route distance
        total_distance = 0.0
        for i in range(len(route_coords) - 1):
            total_distance += _haversine(
                route_coords[i][0],
                route_coords[i][1],
                route_coords[i + 1][0],
                route_coords[i + 1][1],
            )

        # Gather detections near each waypoint (deduplicate by detection_id)
        seen_ids: set[str] = set()
        all_detections: List[dict] = []

        for lat, lon in route_coords:
            nearby = await self.spatial_engine.get_detections_in_radius(
                lat, lon, buffer_m, limit=200
            )
            for det in nearby:
                did = det.get("detection_id")
                if did and did not in seen_ids:
                    seen_ids.add(did)
                    all_detections.append(det)

        by_type: dict[str, int] = {}
        for det in all_detections:
            dt = det.get("detection_type", "unknown")
            by_type[dt] = by_type.get(dt, 0) + 1

        issues_per_100m = (
            (len(all_detections) / total_distance) * 100
            if total_distance > 0
            else 0.0
        )

        return {
            "total_distance_m": round(total_distance, 2),
            "detections": all_detections,
            "detection_count": len(all_detections),
            "issues_per_100m": round(issues_per_100m, 4),
            "by_type": by_type,
        }

    async def calculate_route_walkability(
        self,
        route_coords: List[Tuple[float, float]],
    ) -> float:
        """Return a walkability score from 0 (worst) to 100 (best).

        Scoring method (higher is better):
          - Start at 100
          - Deduct points for issue density (issues_per_100m)
          - Deduct extra for severe types (pothole, missing_ramp)
          - Floor at 0
        """
        analysis = await self.analyze_route(route_coords, buffer_m=50)

        score = 100.0

        # Base density penalty: -5 per issue per 100 m
        score -= analysis["issues_per_100m"] * 5

        # Extra penalty for severe issue types
        severe_types = {"pothole", "missing_ramp", "flooding", "broken_sidewalk"}
        severe_count = sum(
            count
            for dtype, count in analysis["by_type"].items()
            if dtype in severe_types
        )
        score -= severe_count * 2

        return round(max(0.0, min(100.0, score)), 2)
