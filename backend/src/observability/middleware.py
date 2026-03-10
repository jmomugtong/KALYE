"""ASGI middleware that records Prometheus metrics for every HTTP request."""

from __future__ import annotations

import time
from typing import Callable

from starlette.requests import Request
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from backend.src.observability.metrics import (
    kalye_api_latency_seconds,
    kalye_api_requests_total,
)

# Paths that should not be instrumented.
_SKIP_PATHS = {"/health", "/metrics"}


class PrometheusMiddleware:
    """ASGI middleware that records request count and latency to Prometheus."""

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        path = scope.get("path", "")
        if path in _SKIP_PATHS:
            await self.app(scope, receive, send)
            return

        method = scope.get("method", "GET")
        status_code = 500  # default in case of unhandled error

        start = time.perf_counter()

        async def send_wrapper(message: Message) -> None:
            nonlocal status_code
            if message["type"] == "http.response.start":
                status_code = message.get("status", 500)
            await send(message)

        try:
            await self.app(scope, receive, send_wrapper)
        finally:
            elapsed = time.perf_counter() - start
            kalye_api_requests_total.labels(
                endpoint=path,
                method=method,
                status_code=str(status_code),
            ).inc()
            kalye_api_latency_seconds.observe(elapsed)
