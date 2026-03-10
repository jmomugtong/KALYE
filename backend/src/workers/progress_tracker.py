"""Redis-backed progress tracker for Celery tasks."""

from __future__ import annotations

import json
import logging
import time
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)

# TTL for progress entries in Redis (1 hour)
PROGRESS_TTL_SECONDS = 3600


class ProgressTracker:
    """Track task progress in Redis for real-time status queries.

    Uses the Redis URL from application settings. Progress entries are
    stored as JSON hashes keyed by ``task_progress:{task_id}``.
    """

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

    def _key(self, task_id: str) -> str:
        return f"task_progress:{task_id}"

    def update_progress(
        self,
        task_id: str,
        progress: int,
        message: str,
        step: str,
    ) -> None:
        """Update the progress for a task.

        Args:
            task_id: The Celery task ID.
            progress: Percentage complete (0-100).
            message: Human-readable status message.
            step: Current pipeline step name.
        """
        data = {
            "task_id": task_id,
            "progress": progress,
            "message": message,
            "step": step,
            "updated_at": time.time(),
        }

        try:
            self.redis.setex(
                self._key(task_id),
                PROGRESS_TTL_SECONDS,
                json.dumps(data),
            )
        except Exception:
            logger.warning(
                "Failed to update progress for task %s", task_id, exc_info=True
            )

    def get_progress(self, task_id: str) -> Dict[str, Any]:
        """Retrieve the current progress for a task.

        Args:
            task_id: The Celery task ID.

        Returns:
            Progress dict with keys: task_id, progress, message, step,
            updated_at.  Returns a default ``pending`` dict if no entry
            exists.
        """
        try:
            raw = self.redis.get(self._key(task_id))
            if raw is not None:
                return json.loads(raw)
        except Exception:
            logger.warning(
                "Failed to get progress for task %s", task_id, exc_info=True
            )

        return {
            "task_id": task_id,
            "progress": 0,
            "message": "Pending",
            "step": "pending",
            "updated_at": None,
        }
