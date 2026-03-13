"""Redis-backed tiered rate limiter for FastAPI."""
from __future__ import annotations

import logging
from fastapi import HTTPException, Request, status
from src.config.settings import get_settings

logger = logging.getLogger(__name__)

# Tier definitions: (requests, window_seconds)
TIERS = {
    "upload":   (10,  3600),   # 10 uploads/hour  — expensive AI call
    "auth":     (10,   300),   # 10 auth attempts per 5 min — brute force protection
    "default":  (200, 3600),   # 200 requests/hour general
}


class RateLimiter:
    def __init__(self, tier: str = "default") -> None:
        self.tier = tier
        self._redis = None
        self._redis_available: bool | None = None

    def _get_redis(self):
        if self._redis_available is False:
            return None
        if self._redis is None:
            try:
                import redis
                settings = get_settings()
                self._redis = redis.Redis.from_url(
                    settings.redis_url, decode_responses=True, socket_connect_timeout=2
                )
                self._redis.ping()
                self._redis_available = True
            except Exception as exc:
                logger.warning("Redis unavailable, rate limiting disabled: %s", exc)
                self._redis = None
                self._redis_available = False
        return self._redis

    async def __call__(self, request: Request) -> None:
        r = self._get_redis()
        if r is None:
            return

        limit, window = TIERS.get(self.tier, TIERS["default"])
        ip = (request.headers.get("X-Forwarded-For") or "").split(",")[0].strip() \
             or (request.client.host if request.client else "unknown")
        key = f"kalye:rl:{self.tier}:{ip}"

        try:
            current = r.get(key)
            if current is not None and int(current) >= limit:
                raise HTTPException(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    detail=f"Rate limit exceeded ({limit} requests per {window//60} min). Try again later.",
                    headers={"Retry-After": str(window)},
                )
            pipe = r.pipeline()
            pipe.incr(key)
            pipe.expire(key, window)
            pipe.execute()
        except HTTPException:
            raise
        except Exception as exc:
            logger.warning("Rate limiter error (allowing): %s", exc)
