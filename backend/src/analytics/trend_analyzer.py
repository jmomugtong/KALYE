"""Temporal trend analysis for walkability scores."""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List

from sqlalchemy import desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from src.db.models import Location, WalkabilityScore

logger = logging.getLogger(__name__)


class TrendAnalyzer:
    """Analyses walkability score trends over time."""

    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self.session_factory = session_factory

    async def get_weekly_trend(
        self,
        location_id: str,
        weeks: int = 12,
    ) -> List[Dict[str, Any]]:
        """Return weekly walkability scores for *location_id* over the last *weeks* weeks.

        Each entry: {week_start, week_end, score, breakdown}
        """
        async with self.session_factory() as session:
            cutoff = datetime.now(timezone.utc) - timedelta(weeks=weeks)

            stmt = (
                select(WalkabilityScore)
                .where(WalkabilityScore.location_id == location_id)
                .where(WalkabilityScore.calculated_at >= cutoff)
                .order_by(WalkabilityScore.calculated_at)
            )
            result = await session.execute(stmt)
            scores = result.scalars().all()

            # Bucket into weeks
            weekly: Dict[str, Dict[str, Any]] = {}
            for s in scores:
                # ISO calendar week key
                cal = s.calculated_at.isocalendar()
                week_key = f"{cal[0]}-W{cal[1]:02d}"
                if week_key not in weekly:
                    # Compute Monday of that ISO week
                    monday = datetime.fromisocalendar(cal[0], cal[1], 1).replace(
                        tzinfo=timezone.utc
                    )
                    weekly[week_key] = {
                        "week_start": monday.isoformat(),
                        "week_end": (monday + timedelta(days=6)).isoformat(),
                        "scores": [],
                    }
                weekly[week_key]["scores"].append(s.score)

            trend: List[Dict[str, Any]] = []
            for week_key in sorted(weekly.keys()):
                entry = weekly[week_key]
                avg_score = round(sum(entry["scores"]) / len(entry["scores"]), 1)
                trend.append(
                    {
                        "week_start": entry["week_start"],
                        "week_end": entry["week_end"],
                        "score": avg_score,
                        "sample_count": len(entry["scores"]),
                    }
                )

            return trend

    async def identify_improving_areas(self) -> List[Dict[str, Any]]:
        """Return locations whose recent scores show an upward trend.

        Compares the average score of the last 4 weeks against the prior 4 weeks.
        """
        return await self._compare_periods(improving=True)

    async def identify_deteriorating_areas(self) -> List[Dict[str, Any]]:
        """Return locations whose recent scores show a downward trend."""
        return await self._compare_periods(improving=False)

    # ── Internal ─────────────────────────────────────────────────────────

    async def _compare_periods(
        self,
        improving: bool,
    ) -> List[Dict[str, Any]]:
        now = datetime.now(timezone.utc)
        recent_start = now - timedelta(weeks=4)
        prior_start = now - timedelta(weeks=8)

        async with self.session_factory() as session:
            # Recent average per location
            recent_sub = (
                select(
                    WalkabilityScore.location_id,
                    func.avg(WalkabilityScore.score).label("recent_avg"),
                )
                .where(WalkabilityScore.calculated_at >= recent_start)
                .group_by(WalkabilityScore.location_id)
                .subquery()
            )

            # Prior average per location
            prior_sub = (
                select(
                    WalkabilityScore.location_id,
                    func.avg(WalkabilityScore.score).label("prior_avg"),
                )
                .where(WalkabilityScore.calculated_at >= prior_start)
                .where(WalkabilityScore.calculated_at < recent_start)
                .group_by(WalkabilityScore.location_id)
                .subquery()
            )

            stmt = (
                select(
                    Location.location_id,
                    Location.barangay_name,
                    Location.city,
                    recent_sub.c.recent_avg,
                    prior_sub.c.prior_avg,
                )
                .join(recent_sub, Location.location_id == recent_sub.c.location_id)
                .join(prior_sub, Location.location_id == prior_sub.c.location_id)
            )

            if improving:
                stmt = stmt.where(recent_sub.c.recent_avg > prior_sub.c.prior_avg)
                stmt = stmt.order_by(
                    desc(recent_sub.c.recent_avg - prior_sub.c.prior_avg)
                )
            else:
                stmt = stmt.where(recent_sub.c.recent_avg < prior_sub.c.prior_avg)
                stmt = stmt.order_by(
                    recent_sub.c.recent_avg - prior_sub.c.prior_avg
                )

            result = await session.execute(stmt)
            rows = result.all()

            return [
                {
                    "location_id": str(row.location_id),
                    "barangay_name": row.barangay_name,
                    "city": row.city,
                    "recent_avg": round(float(row.recent_avg), 1),
                    "prior_avg": round(float(row.prior_avg), 1),
                    "change": round(
                        float(row.recent_avg) - float(row.prior_avg), 1
                    ),
                }
                for row in rows
            ]
