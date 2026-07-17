from __future__ import annotations

import logging
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from typing import Optional

from adapters.db.user_adapter import UserAdapter
from application.auth_service import AuthService
from api.deps import get_current_user
from domain.entities import User

router = APIRouter(tags=["auth"])
logger = logging.getLogger("stt.auth")

_auth_svc     = AuthService()
_user_adapter = UserAdapter()


# ── Request / response schemas ────────────────────────────────────────────────

class LoginRequest(BaseModel):
    username: str
    password: str


class RegisterRequest(BaseModel):
    username: str
    password: str
    email:    Optional[str] = None


class UserOut(BaseModel):
    id:         int
    username:   str
    email:      Optional[str]
    role:       str
    is_active:  bool
    created_at: str

    @classmethod
    def from_user(cls, u: User) -> "UserOut":
        return cls(
            id=u.id, username=u.username, email=u.email,
            role=u.role.value, is_active=u.is_active, created_at=u.created_at,
        )


class TokenResponse(BaseModel):
    access_token: str
    token_type:   str = "bearer"
    user:         UserOut


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.get(
    "/bootstrap-status",
    summary="Check if first-user setup is needed",
    description="Returns `needs_setup: true` when no users exist yet. Public endpoint — no token required.",
)
async def bootstrap_status():
    return {"needs_setup": _user_adapter.count_users() == 0}


@router.post(
    "/register",
    response_model=TokenResponse,
    summary="Register the first admin user",
    description=(
        "Creates the initial admin account. Only allowed when the users table is empty "
        "(first-run bootstrap). Subsequent registrations must go through the Admin panel."
    ),
    responses={
        403: {"description": "Registration is closed — users already exist"},
        409: {"description": "Username already taken"},
    },
)
async def register(body: RegisterRequest):
    if _user_adapter.count_users() > 0:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Registration is only allowed when no users exist (first-run setup).",
        )
    if _user_adapter.get_by_username(body.username):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Username already taken.")
    hashed = _auth_svc.hash_password(body.password)
    user   = _user_adapter.create_user(body.username, hashed, role="admin", email=body.email)
    token  = _auth_svc.create_token(user)
    return TokenResponse(access_token=token, user=UserOut.from_user(user))


@router.post(
    "/login",
    response_model=TokenResponse,
    summary="Log in and receive a JWT token",
    description="Accepts username + password; returns a bearer token valid for 7 days.",
    responses={401: {"description": "Incorrect username or password"}},
)
async def login(body: LoginRequest):
    user = _user_adapter.get_by_username(body.username)
    if not user or not _auth_svc.verify_password(body.password, user.hashed_pw):
        logger.warning("Failed login attempt for username=%r", body.username)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    if not user.is_active:
        logger.warning("Login attempt for deactivated account username=%r", body.username)
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Account is deactivated.")
    token = _auth_svc.create_token(user)
    logger.info("User logged in: username=%r id=%d", user.username, user.id)
    return TokenResponse(access_token=token, user=UserOut.from_user(user))


@router.get(
    "/me",
    response_model=UserOut,
    summary="Return the currently authenticated user",
    responses={401: {"description": "Token missing or invalid"}},
)
async def me(current_user: User = Depends(get_current_user)):
    return UserOut.from_user(current_user)
