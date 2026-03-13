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

    from src.db.postgres import init_db, dispose_engine
    await init_db()
    print("Database initialized (tables + extensions)")

    # Seed demo admin into both in-memory store AND database
    import uuid as _uuid
    from datetime import datetime as _dt
    from src.api.v1.auth import _users_store
    from src.api.middleware.auth import hash_password
    from src.db.postgres import get_session_factory
    from src.db.models import User, UserRole
    from sqlalchemy import select

    admin_id = "c57d9eac-f27b-4c7d-b9a4-6b90b2e8cefc"
    admin_email = "admin@kalye.ph"
    admin_pw = "KalyeAdmin2026"
    hashed = hash_password(admin_pw)

    # In-memory store (for auth login)
    if admin_email not in _users_store:
        _users_store[admin_email] = {
            "user_id": admin_id,
            "email": admin_email,
            "hashed_password": hashed,
            "role": "admin",
            "created_at": _dt.now(),
        }

    # PostgreSQL (for foreign key references)
    session_factory = get_session_factory()
    async with session_factory() as session:
        existing = await session.execute(
            select(User).where(User.email == admin_email)
        )
        if existing.scalar_one_or_none() is None:
            session.add(User(
                user_id=_uuid.UUID(admin_id),
                email=admin_email,
                hashed_password=hashed,
                role=UserRole.admin,
            ))
            await session.commit()
            print("Seeded demo admin into database: admin@kalye.ph")
        else:
            print("Demo admin already in database")

    yield
    # Shutdown
    await dispose_engine()
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
        allow_origins=["http://localhost:3000", "http://localhost:3002"],
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
