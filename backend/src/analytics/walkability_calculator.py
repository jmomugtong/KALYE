"""Walkability composite scoring engine.

Formula
-------
score = sidewalk_coverage * 0.35
      + (100 - normalized_obstruction) * 0.40
      + ada_compliance * 0.25

Normalized obstruction = (max_density - current) / max_density * 100
"""

from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
from typing import Any, Dict

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from src.db.models import (
    Detection,
    DetectionType,
    Image,
    Location,
    WalkabilityScore,
)

logger = logging.getLogger(__name__)

# Weights
W_SIDEWALK = 0.35
W_OBSTRUCTION = 0.40
W_ADA = 0.25

# The maximum obstruction density (issues per 100 m) used to normalise.
# A location at or above this value receives an obstruction sub-score of 0.
MAX_OBSTRUCTION_DENSITY = 10.0

SCORING_VERSION = "1.0"

# Detection types that count as obstructions
_OBSTRUCTION_TYPES = {
    DetectionType.pothole,
    DetectionType.sidewalk_obstruction,
    DetectionType.broken_sidewalk,
    DetectionType.flooding,
}

# Detection types relevant to ADA compliance (presence is *good*)
_ADA_POSITIVE_TYPES = {
    DetectionType.curb_ramp,
}

# Detection types whose absence or whose presence indicates ADA problems
_ADA_NEGATIVE_TYPES = {
    DetectionType.missing_ramp,
}


class WalkabilityCalculator:
    """Calculates composite walkability scores for a location."""

    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self.session_factory = session_factory

    # ── Public API ───────────────────────────────────────────────────────

    async def calculate_composite_score(self, location_id: str) -> Dict[str, Any]:
        """Return full walkability score payload for *location_id*.

        Returns
        -------
        dict  {score, breakdown, location_id, calculated_at, version}
        """
        sidewalk = await self.calculate_sidewalk_coverage(location_id)
        obstruction = await self.calculate_obstruction_density(location_id)
        ada = await self.calculate_ada_compliance(location_id)

        normalized_obstruction = self._normalize_obstruction(obstruction)

        raw_score = (
            sidewalk * W_SIDEWALK
            + (100.0 - normalized_obstruction) * W_OBSTRUCTION
            + ada * W_ADA
        )
        score = max(0, min(100, round(raw_score)))

        calculated_at = datetime.now(timezone.utc).isoformat()

        breakdown = {
            "sidewalk_coverage": round(sidewalk, 2),
            "obstruction_density": round(obstruction, 4),
            "normalized_obstruction": round(normalized_obstruction, 2),
            "ada_compliance": round(ada, 2),
            "weights": {
                "sidewalk": W_SIDEWALK,
                "obstruction": W_OBSTRUCTION,
                "ada": W_ADA,
            },
        }

        return {
            "score": score,
            "breakdown": breakdown,
            "location_id": location_id,
            "calculated_at": calculated_at,
            "version": SCORING_VERSION,
        }

    async def calculate_sidewalk_coverage(self, location_id: str) -> float:
        """Estimate sidewalk coverage percentage (0-100) for *location_id*.

        Implementation: ratio of images in this location that have at least
        one detection with segmentation metadata indicating sidewalk presence.
        Falls back to a heuristic based on detection types when segmentation
        metadata is unavailable.
        """
        async with self.session_factory() as session:
            loc_uuid = uuid.UUID(location_id)

            # Total images associated with the location's geometry
            total_q = (
                select(func.count(Image.image_id))
                .join(Location, func.ST_Contains(Location.geometry, Image.location))
                .where(Location.location_id == loc_uuid)
            )
            total_result = await session.execute(total_q)
            total_images = total_result.scalar() or 0

            if total_images == 0:
                return 0.0

            # Images that have at least one detection (proxy for sidewalk)
            sidewalk_q = (
                select(func.count(func.distinct(Detection.image_id)))
                .join(Image, Detection.image_id == Image.image_id)
                .join(Location, func.ST_Contains(Location.geometry, Image.location))
                .where(Location.location_id == loc_uuid)
                .where(
                    Detection.detection_type.notin_([
                        DetectionType.pothole,
                        DetectionType.flooding,
                    ])
                )
            )
            sidewalk_result = await session.execute(sidewalk_q)
            sidewalk_count = sidewalk_result.scalar() or 0

            coverage = (sidewalk_count / total_images) * 100.0
            return min(coverage, 100.0)

    async def calculate_obstruction_density(self, location_id: str) -> float:
        """Return number of obstruction-type detections per 100 m of road.

        For now, we approximate: count obstructions / estimated road length
        where road length = number of images * 50 m average spacing.
        Returns issues per 100 m.
        """
        async with self.session_factory() as session:
            loc_uuid = uuid.UUID(location_id)

            obstruction_count_q = (
                select(func.count(Detection.detection_id))
                .join(Image, Detection.image_id == Image.image_id)
                .join(Location, func.ST_Contains(Location.geometry, Image.location))
                .where(Location.location_id == loc_uuid)
                .where(Detection.detection_type.in_(list(_OBSTRUCTION_TYPES)))
                .where(Detection.confidence_score >= 0.70)
            )
            result = await session.execute(obstruction_count_q)
            obstruction_count = result.scalar() or 0

            # Estimate total road length from image count
            image_count_q = (
                select(func.count(Image.image_id))
                .join(Location, func.ST_Contains(Location.geometry, Image.location))
                .where(Location.location_id == loc_uuid)
            )
            img_result = await session.execute(image_count_q)
            image_count = img_result.scalar() or 0

            if image_count == 0:
                return 0.0

            estimated_road_m = image_count * 50.0  # 50 m avg between captures
            density_per_100m = (obstruction_count / estimated_road_m) * 100.0
            return density_per_100m

    async def calculate_ada_compliance(self, location_id: str) -> float:
        """ADA compliance score (0-100) for *location_id*.

        Ratio of positive ADA indicators vs total ADA-relevant detections.
        """
        async with self.session_factory() as session:
            loc_uuid = uuid.UUID(location_id)

            all_ada_types = list(_ADA_POSITIVE_TYPES | _ADA_NEGATIVE_TYPES)

            total_q = (
                select(func.count(Detection.detection_id))
                .join(Image, Detection.image_id == Image.image_id)
                .join(Location, func.ST_Contains(Location.geometry, Image.location))
                .where(Location.location_id == loc_uuid)
                .where(Detection.detection_type.in_(all_ada_types))
                .where(Detection.confidence_score >= 0.70)
            )
            total_result = await session.execute(total_q)
            total_ada = total_result.scalar() or 0

            if total_ada == 0:
                return 50.0  # neutral when no data

            positive_q = (
                select(func.count(Detection.detection_id))
                .join(Image, Detection.image_id == Image.image_id)
                .join(Location, func.ST_Contains(Location.geometry, Image.location))
                .where(Location.location_id == loc_uuid)
                .where(Detection.detection_type.in_(list(_ADA_POSITIVE_TYPES)))
                .where(Detection.confidence_score >= 0.70)
            )
            pos_result = await session.execute(positive_q)
            positive_ada = pos_result.scalar() or 0

            return (positive_ada / total_ada) * 100.0

    # ── Helpers ───────────────────────────────────────────────────────────

    @staticmethod
    def _normalize_obstruction(density: float) -> float:
        """Normalise obstruction density to 0-100.

        0 density   -> 0 (best, contributes 100 to the score component)
        >=MAX       -> 100 (worst, contributes 0)
        """
        if density <= 0:
            return 0.0
        if density >= MAX_OBSTRUCTION_DENSITY:
            return 100.0
        return (density / MAX_OBSTRUCTION_DENSITY) * 100.0
