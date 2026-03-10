"""Redis-backed rate limiter for FastAPI."""

from __future__ import annotations

import logging
import time

from fastapi import HTTPException, Request, status

from src.config.settings import get_settings

logger = logging.getLogger(__name__)


class RateLimiter:
    """Sliding-window rate limiter using Redis.

    Usage as a FastAPI dependency::

        limiter = RateLimiter(requests_per_hour=100)

        @app.get("/endpoint", dependencies=[Depends(limiter)])
        async def endpoint(): ...
    """

    def __init__(self, requests_per_hour: int = 100) -> None:
        self.requests_per_hour = requests_per_hour
        self._redis = None
        self._redis_available: bool | None = None

    def _get_redis(self):
        """Lazy-initialise Redis connection; return None if unavailable."""
        if self._redis_available is False:
            return None

        if self._redis is None:
            try:
                import redis

                settings = get_settings()
                self._redis = redis.Redis.from_url(
                    settings.redis_url,
                    decode_responses=True,
                    socket_connect_timeout=2,
                )
                self._redis.ping()
                self._redis_available = True
            except Exception as exc:
                logger.warning("Redis unavailable, rate limiting disabled: %s", exc)
                self._redis = None
                self._redis_available = False
                return None

        return self._redis

    async def __call__(self, request: Request) -> None:
        """Check rate limit for the requesting IP."""
        r = self._get_redis()
        if r is None:
            # Redis not available: let request through
            return

        client_ip = request.client.host if request.client else "unknown"
        key = f"kalye:rate_limit:{client_ip}"
        window = 3600  # 1 hour in seconds

        try:
            current = r.get(key)
            if current is not None and int(current) >= self.requests_per_hour:
                raise HTTPException(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    detail="Rate limit exceeded. Try again later.",
                )

            pipe = r.pipeline()
            pipe.incr(key)
            pipe.expire(key, window)
            pipe.execute()
        except HTTPException:
            raise
        except Exception as exc:
            logger.warning("Rate limiter error (allowing request): %s", exc)
