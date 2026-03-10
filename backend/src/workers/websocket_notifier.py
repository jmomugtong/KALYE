"""Redis pub/sub notifier for broadcasting processing progress over WebSockets.

Celery workers run in separate processes (often on different machines) and
cannot directly access the FastAPI WebSocket manager.  This notifier publishes
progress messages to a Redis channel.  The API process subscribes to the
channel and forwards messages to the appropriate WebSocket room.
"""

from __future__ import annotations

import json
import logging
import time
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)

# Redis channel prefix for WebSocket progress messages
CHANNEL_PREFIX = "ws:progress:"


class WebSocketNotifier:
    """Publish processing progress to Redis so the API layer can relay it."""

    def __init__(self, redis_client: Optional[Any] = None) -> None:
        self._redis = redis_client

    @property
    def redis(self) -> Any:
        """Lazily connect to Redis using application settings."""
        if self._redis is None:
            import redis

            from src.config.settings import get_settings

            settings = get_settings()
            self._redis = redis.Redis.from_url(
                settings.redis_url, decode_responses=True
            )
        return self._redis

    def _channel(self, image_id: str) -> str:
        return f"{CHANNEL_PREFIX}{image_id}"

    def _publish(self, image_id: str, message: dict) -> None:
        """Publish *message* to the Redis channel for *image_id*."""
        try:
            self.redis.publish(self._channel(image_id), json.dumps(message))
        except Exception:
            logger.warning(
                "Failed to publish WebSocket notification for image %s",
                image_id,
                exc_info=True,
            )

    # ── Public API ──────────────────────────────────────────────────────

    def notify_progress(
        self,
        image_id: str,
        stage: str,
        progress: int,
        message: str,
    ) -> None:
        """Notify listeners of processing progress.

        Args:
            image_id: The image being processed.
            stage: Pipeline stage (``detection``, ``segmentation``, ``captioning``).
            progress: Percentage complete (0-100).
            message: Human-readable status text.
        """
        stage_type_map = {
            "detection": "detection_progress",
            "segmentation": "segmentation_progress",
            "captioning": "captioning_progress",
        }
        msg_type = stage_type_map.get(stage, "detection_progress")

        self._publish(image_id, {
            "type": msg_type,
            "image_id": image_id,
            "stage": stage,
            "progress": progress,
            "message": message,
            "timestamp": _iso_now(),
        })

    def notify_complete(
        self,
        image_id: str,
        results_summary: Dict[str, Any],
    ) -> None:
        """Notify listeners that processing completed successfully."""
        self._publish(image_id, {
            "type": "processing_complete",
            "image_id": image_id,
            "results_summary": results_summary,
            "timestamp": _iso_now(),
        })

    def notify_failed(self, image_id: str, error: str) -> None:
        """Notify listeners that processing failed."""
        self._publish(image_id, {
            "type": "processing_failed",
            "image_id": image_id,
            "error": error,
            "timestamp": _iso_now(),
        })


def _iso_now() -> str:
    from datetime import datetime, timezone

    return datetime.now(timezone.utc).isoformat()
