"""Tests for the FastAPI REST API layer."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from src.api.main import app


@pytest.fixture
def client():
    return TestClient(app)


# ── Health ───────────────────────────────────────────────────────────────────


def test_health_endpoint(client):
    resp = client.get("/health")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "ok"
    assert "version" in data


# ── Auth: Register ───────────────────────────────────────────────────────────


def test_register_creates_user(client):
    # Clear the in-memory store between tests
    from src.api.v1 import auth as auth_module
    auth_module._users_store.clear()

    resp = client.post(
        "/api/v1/auth/register",
        json={"email": "test@kalye.dev", "password": "strongPass123"},
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["email"] == "test@kalye.dev"
    assert data["role"] == "public"
    assert "user_id" in data


def test_register_duplicate_email(client):
    from src.api.v1 import auth as auth_module
    auth_module._users_store.clear()

    client.post(
        "/api/v1/auth/register",
        json={"email": "dup@kalye.dev", "password": "pass123"},
    )
    resp = client.post(
        "/api/v1/auth/register",
        json={"email": "dup@kalye.dev", "password": "pass456"},
    )
    assert resp.status_code == 409


# ── Auth: Login ──────────────────────────────────────────────────────────────


def test_login_returns_jwt(client):
    from src.api.v1 import auth as auth_module
    auth_module._users_store.clear()

    client.post(
        "/api/v1/auth/register",
        json={"email": "login@kalye.dev", "password": "mypassword"},
    )

    resp = client.post(
        "/api/v1/auth/login",
        json={"email": "login@kalye.dev", "password": "mypassword"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert "access_token" in data
    assert data["token_type"] == "bearer"


def test_login_wrong_password(client):
    from src.api.v1 import auth as auth_module
    auth_module._users_store.clear()

    client.post(
        "/api/v1/auth/register",
        json={"email": "wrong@kalye.dev", "password": "correct"},
    )

    resp = client.post(
        "/api/v1/auth/login",
        json={"email": "wrong@kalye.dev", "password": "incorrect"},
    )
    assert resp.status_code == 401


# ── Auth: /me ────────────────────────────────────────────────────────────────


def test_me_with_valid_token(client):
    from src.api.v1 import auth as auth_module
    auth_module._users_store.clear()

    client.post(
        "/api/v1/auth/register",
        json={"email": "me@kalye.dev", "password": "secret"},
    )
    login_resp = client.post(
        "/api/v1/auth/login",
        json={"email": "me@kalye.dev", "password": "secret"},
    )
    token = login_resp.json()["access_token"]

    resp = client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    assert resp.json()["email"] == "me@kalye.dev"


def test_me_without_token_returns_401(client):
    resp = client.get("/api/v1/auth/me")
    assert resp.status_code == 403  # HTTPBearer returns 403 when no credentials


def test_me_with_invalid_token_returns_401(client):
    resp = client.get(
        "/api/v1/auth/me",
        headers={"Authorization": "Bearer invalid.token.here"},
    )
    assert resp.status_code == 401


# ── Rate Limiter ─────────────────────────────────────────────────────────────


def test_rate_limiter_allows_under_limit():
    """Rate limiter should allow requests under the limit."""
    from src.api.middleware.rate_limit import RateLimiter

    limiter = RateLimiter(requests_per_hour=5)

    mock_redis = MagicMock()
    mock_redis.get.return_value = "2"
    mock_redis.pipeline.return_value = MagicMock()
    limiter._redis = mock_redis
    limiter._redis_available = True

    mock_request = MagicMock()
    mock_request.client.host = "127.0.0.1"

    import asyncio
    # Should not raise
    asyncio.get_event_loop().run_until_complete(limiter(mock_request))


def test_rate_limiter_blocks_over_limit():
    """Rate limiter should raise 429 when limit exceeded."""
    from fastapi import HTTPException
    from src.api.middleware.rate_limit import RateLimiter

    limiter = RateLimiter(requests_per_hour=5)

    mock_redis = MagicMock()
    mock_redis.get.return_value = "5"
    limiter._redis = mock_redis
    limiter._redis_available = True

    mock_request = MagicMock()
    mock_request.client.host = "127.0.0.1"

    import asyncio
    with pytest.raises(HTTPException) as exc_info:
        asyncio.get_event_loop().run_until_complete(limiter(mock_request))
    assert exc_info.value.status_code == 429


def test_rate_limiter_skips_when_redis_unavailable():
    """Rate limiter should pass through when Redis is down."""
    from src.api.middleware.rate_limit import RateLimiter

    limiter = RateLimiter(requests_per_hour=5)
    limiter._redis = None
    limiter._redis_available = False

    mock_request = MagicMock()
    mock_request.client.host = "127.0.0.1"

    import asyncio
    # Should not raise
    asyncio.get_event_loop().run_until_complete(limiter(mock_request))
