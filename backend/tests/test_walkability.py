"""Tests for the walkability scoring engine."""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.analytics.walkability_calculator import (
    MAX_OBSTRUCTION_DENSITY,
    W_ADA,
    W_OBSTRUCTION,
    W_SIDEWALK,
    WalkabilityCalculator,
)
from src.analytics.trend_analyzer import TrendAnalyzer


# ── Helpers ──────────────────────────────────────────────────────────────────


def _make_session_factory(scalars: list | None = None):
    """Create a mock async session factory that returns predetermined scalar values."""
    scalar_iter = iter(scalars or [])

    mock_result = MagicMock()
    mock_result.scalar = lambda: next(scalar_iter, 0)

    mock_session = AsyncMock()
    mock_session.execute = AsyncMock(return_value=mock_result)
    mock_session.__aenter__ = AsyncMock(return_value=mock_session)
    mock_session.__aexit__ = AsyncMock(return_value=False)

    factory = MagicMock()
    factory.return_value = mock_session
    return factory


# ── WalkabilityCalculator tests ──────────────────────────────────────────────


class TestWalkabilityCalculator:
    """Unit tests for WalkabilityCalculator."""

    @pytest.mark.asyncio
    async def test_composite_score_calculation(self):
        """Composite score combines sidewalk, obstruction, and ADA sub-scores."""
        location_id = str(uuid.uuid4())

        calc = WalkabilityCalculator(session_factory=MagicMock())

        # Patch sub-score methods to return known values
        with (
            patch.object(calc, "calculate_sidewalk_coverage", new_callable=AsyncMock, return_value=80.0),
            patch.object(calc, "calculate_obstruction_density", new_callable=AsyncMock, return_value=2.0),
            patch.object(calc, "calculate_ada_compliance", new_callable=AsyncMock, return_value=60.0),
        ):
            result = await calc.calculate_composite_score(location_id)

        assert "score" in result
        assert "breakdown" in result
        assert result["location_id"] == location_id
        assert result["version"] == "1.0"
        assert "calculated_at" in result

        # Verify formula
        norm_obs = (2.0 / MAX_OBSTRUCTION_DENSITY) * 100.0
        expected_raw = 80.0 * W_SIDEWALK + (100.0 - norm_obs) * W_OBSTRUCTION + 60.0 * W_ADA
        assert result["score"] == round(expected_raw)

    @pytest.mark.asyncio
    async def test_sidewalk_coverage_no_images(self):
        """Zero images should produce 0% coverage."""
        factory = _make_session_factory(scalars=[0])
        calc = WalkabilityCalculator(session_factory=factory)

        coverage = await calc.calculate_sidewalk_coverage(str(uuid.uuid4()))
        assert coverage == 0.0

    @pytest.mark.asyncio
    async def test_sidewalk_coverage_with_images(self):
        """Sidewalk coverage = (sidewalk images / total images) * 100."""
        # total_images=10, sidewalk_count=7 -> 70%
        factory = _make_session_factory(scalars=[10, 7])
        calc = WalkabilityCalculator(session_factory=factory)

        coverage = await calc.calculate_sidewalk_coverage(str(uuid.uuid4()))
        assert coverage == 70.0

    @pytest.mark.asyncio
    async def test_obstruction_density_normalization(self):
        """Normalization maps 0 -> 0, MAX -> 100."""
        calc = WalkabilityCalculator(session_factory=MagicMock())

        assert calc._normalize_obstruction(0) == 0.0
        assert calc._normalize_obstruction(MAX_OBSTRUCTION_DENSITY) == 100.0
        assert calc._normalize_obstruction(MAX_OBSTRUCTION_DENSITY / 2) == 50.0
        # Above max clamps to 100
        assert calc._normalize_obstruction(MAX_OBSTRUCTION_DENSITY * 2) == 100.0

    @pytest.mark.asyncio
    async def test_obstruction_density_no_images(self):
        """Zero images should produce 0.0 density."""
        # obstruction_count=5, image_count=0
        factory = _make_session_factory(scalars=[5, 0])
        calc = WalkabilityCalculator(session_factory=factory)

        density = await calc.calculate_obstruction_density(str(uuid.uuid4()))
        assert density == 0.0

    @pytest.mark.asyncio
    async def test_ada_compliance_no_detections(self):
        """No ADA detections returns neutral 50%."""
        factory = _make_session_factory(scalars=[0])
        calc = WalkabilityCalculator(session_factory=factory)

        ada = await calc.calculate_ada_compliance(str(uuid.uuid4()))
        assert ada == 50.0

    @pytest.mark.asyncio
    async def test_ada_compliance_with_detections(self):
        """ADA compliance = positive / total * 100."""
        # total_ada=10, positive_ada=8 -> 80%
        factory = _make_session_factory(scalars=[10, 8])
        calc = WalkabilityCalculator(session_factory=factory)

        ada = await calc.calculate_ada_compliance(str(uuid.uuid4()))
        assert ada == 80.0

    @pytest.mark.asyncio
    async def test_score_is_0_to_100(self):
        """The composite score must always be within [0, 100]."""
        calc = WalkabilityCalculator(session_factory=MagicMock())

        # Best possible
        with (
            patch.object(calc, "calculate_sidewalk_coverage", new_callable=AsyncMock, return_value=100.0),
            patch.object(calc, "calculate_obstruction_density", new_callable=AsyncMock, return_value=0.0),
            patch.object(calc, "calculate_ada_compliance", new_callable=AsyncMock, return_value=100.0),
        ):
            best = await calc.calculate_composite_score(str(uuid.uuid4()))
        assert 0 <= best["score"] <= 100

        # Worst possible
        with (
            patch.object(calc, "calculate_sidewalk_coverage", new_callable=AsyncMock, return_value=0.0),
            patch.object(calc, "calculate_obstruction_density", new_callable=AsyncMock, return_value=999.0),
            patch.object(calc, "calculate_ada_compliance", new_callable=AsyncMock, return_value=0.0),
        ):
            worst = await calc.calculate_composite_score(str(uuid.uuid4()))
        assert 0 <= worst["score"] <= 100


# ── TrendAnalyzer tests ─────────────────────────────────────────────────────


class TestTrendAnalyzer:
    """Unit tests for TrendAnalyzer."""

    @pytest.mark.asyncio
    async def test_weekly_trend_empty(self):
        """No scores returns an empty trend list."""
        mock_result = MagicMock()
        mock_result.scalars = MagicMock(return_value=MagicMock(all=MagicMock(return_value=[])))

        mock_session = AsyncMock()
        mock_session.execute = AsyncMock(return_value=mock_result)
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=False)

        factory = MagicMock()
        factory.return_value = mock_session

        analyzer = TrendAnalyzer(session_factory=factory)
        trend = await analyzer.get_weekly_trend(str(uuid.uuid4()), weeks=4)
        assert trend == []

    @pytest.mark.asyncio
    async def test_weekly_trend_bucketing(self):
        """Scores are bucketed into ISO weeks and averaged."""
        now = datetime.now(timezone.utc)
        # Create fake WalkabilityScore objects
        scores = []
        for i in range(3):
            s = MagicMock()
            s.calculated_at = now - timedelta(days=i)
            s.score = 60 + i * 10  # 60, 70, 80
            scores.append(s)

        mock_result = MagicMock()
        mock_result.scalars = MagicMock(return_value=MagicMock(all=MagicMock(return_value=scores)))

        mock_session = AsyncMock()
        mock_session.execute = AsyncMock(return_value=mock_result)
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=False)

        factory = MagicMock()
        factory.return_value = mock_session

        analyzer = TrendAnalyzer(session_factory=factory)
        trend = await analyzer.get_weekly_trend(str(uuid.uuid4()), weeks=4)

        # Should have at least 1 week bucket
        assert len(trend) >= 1
        for entry in trend:
            assert "week_start" in entry
            assert "week_end" in entry
            assert "score" in entry
            assert "sample_count" in entry
