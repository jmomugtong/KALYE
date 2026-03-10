"""Tests for the geospatial analytics module.

All database interactions are mocked — no live PostGIS instance required.
"""

import uuid
from collections import namedtuple
from unittest.mock import AsyncMock, MagicMock, patch

import numpy as np
import pytest

from src.geo.spatial_queries import SpatialQueryEngine
from src.geo.clustering import DetectionClusterer
from src.geo.route_analyzer import RouteAnalyzer, _haversine
from src.geo.barangay_stats import BarangayStatsCalculator


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_detection(
    lat: float = 14.5995,
    lon: float = 120.9842,
    detection_type: str = "pothole",
    confidence: float = 0.85,
    distance_m: float | None = None,
) -> dict:
    d = {
        "detection_id": str(uuid.uuid4()),
        "detection_type": detection_type,
        "confidence_score": confidence,
        "bounding_box": {"x": 0, "y": 0, "w": 50, "h": 50},
        "caption": "a pothole on the road",
        "lat": lat,
        "lon": lon,
    }
    if distance_m is not None:
        d["distance_m"] = distance_m
    return d


class _Row:
    """Mimics a SQLAlchemy Row object with a _mapping attribute."""

    def __init__(self, mapping: dict):
        self._mapping = mapping


def _mock_session_factory(rows):
    """Return an async_sessionmaker-like callable that yields a mock session."""
    mock_result = MagicMock()
    mock_result.fetchall.return_value = [_Row(r) for r in rows]
    mock_result.fetchone.return_value = _Row(rows[0]) if rows else None
    mock_result.scalar.return_value = rows[0] if rows and not isinstance(rows[0], dict) else None

    mock_session = AsyncMock()
    mock_session.execute.return_value = mock_result

    # Make the factory an async context manager that yields mock_session
    factory = MagicMock()
    ctx = AsyncMock()
    ctx.__aenter__.return_value = mock_session
    ctx.__aexit__.return_value = None
    factory.return_value = ctx
    return factory


# ===========================================================================
# SpatialQueryEngine tests
# ===========================================================================

class TestSpatialQueryEngine:

    @pytest.mark.asyncio
    async def test_get_detections_in_radius(self):
        rows = [
            {"detection_id": "abc", "detection_type": "pothole",
             "confidence_score": 0.9, "bounding_box": {}, "caption": None,
             "lat": 14.60, "lon": 120.98, "distance_m": 42.5},
        ]
        factory = _mock_session_factory(rows)
        engine = SpatialQueryEngine(factory)

        results = await engine.get_detections_in_radius(14.5995, 120.9842, 500)
        assert len(results) == 1
        assert results[0]["detection_id"] == "abc"
        assert results[0]["distance_m"] == 42.5

    @pytest.mark.asyncio
    async def test_get_detections_in_bbox(self):
        rows = [
            {"detection_id": "d1", "detection_type": "pothole",
             "confidence_score": 0.8, "bounding_box": {}, "caption": None,
             "lat": 14.60, "lon": 120.98},
            {"detection_id": "d2", "detection_type": "missing_ramp",
             "confidence_score": 0.75, "bounding_box": {}, "caption": None,
             "lat": 14.61, "lon": 120.99},
        ]
        factory = _mock_session_factory(rows)
        engine = SpatialQueryEngine(factory)

        results = await engine.get_detections_in_bbox(120.97, 14.59, 121.00, 14.62)
        assert len(results) == 2

    @pytest.mark.asyncio
    async def test_get_detections_in_barangay(self):
        rows = [
            {"detection_id": "b1", "detection_type": "sidewalk_obstruction",
             "confidence_score": 0.82, "bounding_box": {}, "caption": None,
             "lat": 14.55, "lon": 120.99},
        ]
        factory = _mock_session_factory(rows)
        engine = SpatialQueryEngine(factory)

        results = await engine.get_detections_in_barangay("Barangay 1")
        assert len(results) == 1
        assert results[0]["detection_type"] == "sidewalk_obstruction"

    @pytest.mark.asyncio
    async def test_calculate_distance(self):
        # Mock returns a scalar float
        distance_value = 1234.56
        factory = _mock_session_factory([distance_value])
        # Override scalar return for this test
        mock_session = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar.return_value = distance_value
        mock_session.execute.return_value = mock_result

        ctx = AsyncMock()
        ctx.__aenter__.return_value = mock_session
        ctx.__aexit__.return_value = None
        factory = MagicMock()
        factory.return_value = ctx

        engine = SpatialQueryEngine(factory)
        dist = await engine.calculate_distance(14.5, 120.9, 14.6, 121.0)
        assert dist == 1234.56

    @pytest.mark.asyncio
    async def test_get_nearest_detections_ordering(self):
        rows = [
            {"detection_id": "n1", "detection_type": "pothole",
             "confidence_score": 0.9, "bounding_box": {}, "caption": None,
             "lat": 14.60, "lon": 120.98, "distance_m": 10.0},
            {"detection_id": "n2", "detection_type": "pothole",
             "confidence_score": 0.7, "bounding_box": {}, "caption": None,
             "lat": 14.62, "lon": 121.00, "distance_m": 500.0},
        ]
        factory = _mock_session_factory(rows)
        engine = SpatialQueryEngine(factory)

        results = await engine.get_nearest_detections(14.5995, 120.9842, limit=2)
        assert len(results) == 2
        assert results[0]["distance_m"] < results[1]["distance_m"]


# ===========================================================================
# DetectionClusterer tests
# ===========================================================================

class TestDetectionClusterer:

    def test_cluster_detections_groups_nearby(self):
        """Points within eps_meters should cluster together."""
        clusterer = DetectionClusterer()
        # Three nearby points and one far away
        detections = [
            _make_detection(lat=14.5995, lon=120.9842),
            _make_detection(lat=14.5996, lon=120.9843),
            _make_detection(lat=14.5997, lon=120.9844),
            _make_detection(lat=15.0000, lon=121.5000),  # far
        ]
        clusters = clusterer.cluster_detections(detections, eps_meters=200, min_samples=2)

        # Expect at least one real cluster (id >= 0) and possibly noise (id = -1)
        real_clusters = [c for c in clusters if c["cluster_id"] >= 0]
        assert len(real_clusters) >= 1
        # The close trio should form a cluster of 3
        assert any(c["count"] == 3 for c in real_clusters)

    def test_cluster_detections_separates_far_points(self):
        clusterer = DetectionClusterer()
        detections = [
            _make_detection(lat=14.0, lon=120.0),
            _make_detection(lat=14.0001, lon=120.0001),
            _make_detection(lat=14.0002, lon=120.0002),
            _make_detection(lat=16.0, lon=122.0),
            _make_detection(lat=16.0001, lon=122.0001),
            _make_detection(lat=16.0002, lon=122.0002),
        ]
        clusters = clusterer.cluster_detections(detections, eps_meters=500, min_samples=2)
        real_clusters = [c for c in clusters if c["cluster_id"] >= 0]
        assert len(real_clusters) == 2

    def test_cluster_detections_empty_input(self):
        clusterer = DetectionClusterer()
        assert clusterer.cluster_detections([]) == []

    def test_generate_heatmap_data(self):
        clusterer = DetectionClusterer()
        detections = [
            _make_detection(lat=14.5995, lon=120.9842, confidence=0.90),
            _make_detection(lat=14.5996, lon=120.9843, confidence=0.80),
            _make_detection(lat=14.6100, lon=121.0000, confidence=0.70),
        ]
        heatmap = clusterer.generate_heatmap_data(detections, grid_size=0.001)

        # At least two distinct grid cells
        assert len(heatmap) >= 2
        # Sorted by count descending
        counts = [h["count"] for h in heatmap]
        assert counts == sorted(counts, reverse=True)
        # First cell should have the two nearby points
        assert heatmap[0]["count"] == 2
        assert heatmap[0]["avg_confidence"] is not None

    def test_generate_heatmap_data_empty(self):
        clusterer = DetectionClusterer()
        assert clusterer.generate_heatmap_data([]) == []


# ===========================================================================
# RouteAnalyzer tests
# ===========================================================================

class TestRouteAnalyzer:

    @pytest.mark.asyncio
    async def test_analyze_route_detections_along_route(self):
        det1 = _make_detection(detection_type="pothole")
        det2 = _make_detection(detection_type="missing_ramp")

        mock_engine = AsyncMock(spec=SpatialQueryEngine)
        # First waypoint returns det1, second returns det1+det2
        mock_engine.get_detections_in_radius.side_effect = [
            [det1],
            [det1, det2],  # det1 duplicated — should be deduplicated
        ]

        analyzer = RouteAnalyzer(mock_engine)
        result = await analyzer.analyze_route(
            [(14.5995, 120.9842), (14.6050, 120.9900)],
            buffer_m=50,
        )

        assert result["detection_count"] == 2
        assert result["total_distance_m"] > 0
        assert "pothole" in result["by_type"]
        assert "missing_ramp" in result["by_type"]
        assert result["issues_per_100m"] >= 0

    @pytest.mark.asyncio
    async def test_analyze_route_single_point(self):
        mock_engine = AsyncMock(spec=SpatialQueryEngine)
        analyzer = RouteAnalyzer(mock_engine)

        result = await analyzer.analyze_route([(14.5995, 120.9842)])
        assert result["total_distance_m"] == 0.0
        assert result["detection_count"] == 0

    @pytest.mark.asyncio
    async def test_calculate_route_walkability(self):
        """A route with no issues should score 100; many issues should lower the score."""
        mock_engine = AsyncMock(spec=SpatialQueryEngine)
        mock_engine.get_detections_in_radius.return_value = []

        analyzer = RouteAnalyzer(mock_engine)
        score = await analyzer.calculate_route_walkability(
            [(14.5995, 120.9842), (14.6050, 120.9900)]
        )
        assert score == 100.0

    @pytest.mark.asyncio
    async def test_calculate_route_walkability_with_issues(self):
        detections = [
            _make_detection(detection_type="pothole"),
            _make_detection(detection_type="pothole"),
            _make_detection(detection_type="missing_ramp"),
            _make_detection(detection_type="sidewalk_obstruction"),
        ]
        # Give each a unique id for deduplication
        for d in detections:
            d["detection_id"] = str(uuid.uuid4())

        mock_engine = AsyncMock(spec=SpatialQueryEngine)
        mock_engine.get_detections_in_radius.return_value = detections

        analyzer = RouteAnalyzer(mock_engine)
        score = await analyzer.calculate_route_walkability(
            [(14.5995, 120.9842), (14.6050, 120.9900)]
        )
        assert 0 <= score < 100

    def test_haversine_accuracy(self):
        """Haversine for known distance: Manila to Quezon City ~12 km."""
        dist = _haversine(14.5995, 120.9842, 14.6760, 121.0437)
        assert 8000 < dist < 15000  # roughly 10 km


# ===========================================================================
# BarangayStatsCalculator tests
# ===========================================================================

class TestBarangayStatsCalculator:

    @pytest.mark.asyncio
    async def test_calculate_stats(self):
        agg_row = {
            "barangay_name": "Barangay 1",
            "total_detections": 42,
            "avg_confidence": 0.8123,
            "area_km2": 1.5678,
        }
        type_rows = [
            {"detection_type": "pothole", "cnt": 20},
            {"detection_type": "missing_ramp", "cnt": 22},
        ]

        # Build a session mock that returns different results for two execute calls
        mock_session = AsyncMock()

        agg_result = MagicMock()
        agg_result.fetchone.return_value = _Row(agg_row)

        type_result = MagicMock()
        type_result.fetchall.return_value = [_Row(r) for r in type_rows]

        mock_session.execute.side_effect = [agg_result, type_result]

        ctx = AsyncMock()
        ctx.__aenter__.return_value = mock_session
        ctx.__aexit__.return_value = None
        factory = MagicMock()
        factory.return_value = ctx

        calc = BarangayStatsCalculator(factory)
        stats = await calc.calculate_stats("Barangay 1")

        assert stats["barangay_name"] == "Barangay 1"
        assert stats["total_detections"] == 42
        assert stats["by_type"]["pothole"] == 20
        assert stats["by_type"]["missing_ramp"] == 22
        assert stats["avg_confidence"] == 0.8123
        assert stats["area_km2"] == 1.5678

    @pytest.mark.asyncio
    async def test_calculate_stats_empty(self):
        mock_session = AsyncMock()
        agg_result = MagicMock()
        agg_result.fetchone.return_value = None
        mock_session.execute.return_value = agg_result

        ctx = AsyncMock()
        ctx.__aenter__.return_value = mock_session
        ctx.__aexit__.return_value = None
        factory = MagicMock()
        factory.return_value = ctx

        calc = BarangayStatsCalculator(factory)
        stats = await calc.calculate_stats("Nonexistent")
        assert stats["total_detections"] == 0
        assert stats["by_type"] == {}

    @pytest.mark.asyncio
    async def test_get_all_rankings_ordering(self):
        rows = [
            {"barangay_name": "Dense Brgy", "total_detections": 100,
             "avg_confidence": 0.85, "area_km2": 0.5},
            {"barangay_name": "Sparse Brgy", "total_detections": 10,
             "avg_confidence": 0.70, "area_km2": 5.0},
        ]
        factory = _mock_session_factory(rows)
        calc = BarangayStatsCalculator(factory)

        rankings = await calc.get_all_rankings()
        assert len(rankings) == 2
        # First should have higher density
        assert rankings[0]["density_per_km2"] >= rankings[1]["density_per_km2"]
        assert rankings[0]["barangay_name"] == "Dense Brgy"
