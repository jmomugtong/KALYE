"""FastAPI application factory for KALYE API."""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from src.config.settings import get_settings


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    settings = get_settings()
    print(f"Starting KALYE API ({settings.app_env})")
    yield
    # Shutdown
    print("Shutting down KALYE API")


def create_app() -> FastAPI:
    settings = get_settings()

    app = FastAPI(
        title="KALYE API",
        description="AI-powered walkability intelligence for Metro Manila",
        version="0.1.0",
        lifespan=lifespan,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:3000"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # ── Health ───────────────────────────────────────────────────────────
    @app.get("/health")
    async def health():
        return {"status": "ok", "version": "0.1.0"}

    @app.get("/metrics")
    async def metrics():
        """Placeholder for Prometheus metrics export."""
        return {"status": "metrics endpoint placeholder"}

    # ── Register v1 routers ──────────────────────────────────────────────
    from src.api.v1.images import router as images_router
    from src.api.v1.detections import router as detections_router
    from src.api.v1.analytics import router as analytics_router
    from src.api.v1.auth import router as auth_router
    from src.api.v1.rag import router as rag_router

    app.include_router(images_router)
    app.include_router(detections_router)
    app.include_router(analytics_router)
    app.include_router(auth_router)
    app.include_router(rag_router)

    # ── Rate limiter (soft dependency on Redis) ──────────────────────────
    try:
        from src.api.middleware.rate_limit import RateLimiter

        _limiter = RateLimiter(requests_per_hour=100)
        app.state.rate_limiter = _limiter
    except Exception:
        pass  # Redis unavailable; proceed without rate limiting

    return app


app = create_app()
