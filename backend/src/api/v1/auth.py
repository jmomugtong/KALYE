"""Authentication endpoints: register, login, current user."""

from __future__ import annotations

import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, EmailStr

from src.api.middleware.auth import create_access_token, get_current_user, verify_password, hash_password

router = APIRouter(prefix="/api/v1/auth", tags=["auth"])

# ── In-memory user store (placeholder until DB wiring) ───────────────────────
# Keys: email -> {user_id, email, hashed_password, role, created_at}
_users_store: dict[str, dict] = {}


# ── Request / Response Models ────────────────────────────────────────────────


class RegisterRequest(BaseModel):
    email: EmailStr
    password: str


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class UserResponse(BaseModel):
    user_id: str
    email: str
    role: str
    created_at: datetime


# ── Endpoints ────────────────────────────────────────────────────────────────


@router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def register(body: RegisterRequest):
    """Create a new user account."""
    if body.email in _users_store:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Email already registered",
        )

    user_id = str(uuid.uuid4())
    now = datetime.utcnow()

    _users_store[body.email] = {
        "user_id": user_id,
        "email": body.email,
        "hashed_password": hash_password(body.password),
        "role": "public",
        "created_at": now,
    }

    return UserResponse(
        user_id=user_id,
        email=body.email,
        role="public",
        created_at=now,
    )


@router.post("/login", response_model=TokenResponse)
async def login(body: LoginRequest):
    """Authenticate and return a JWT."""
    user = _users_store.get(body.email)
    if user is None or not verify_password(body.password, user["hashed_password"]):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
        )

    token = create_access_token({"sub": user["email"], "user_id": user["user_id"]})
    return TokenResponse(access_token=token)


@router.get("/me", response_model=UserResponse)
async def me(current_user: dict = Depends(get_current_user)):
    """Return the currently authenticated user."""
    user = _users_store.get(current_user["sub"])
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )
    return UserResponse(
        user_id=user["user_id"],
        email=user["email"],
        role=user["role"],
        created_at=user["created_at"],
    )
