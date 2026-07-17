from __future__ import annotations

from fastapi import Depends, HTTPException, Query, status
from fastapi.security import OAuth2PasswordBearer

from adapters.db.user_adapter import UserAdapter
from application.auth_service import AuthService
from domain.entities import User, UserRole

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login")

_auth_svc    = AuthService()
_user_adapter = UserAdapter()

_credentials_exc = HTTPException(
    status_code=status.HTTP_401_UNAUTHORIZED,
    detail="Could not validate credentials",
    headers={"WWW-Authenticate": "Bearer"},
)


def _resolve_token(token: str) -> User:
    try:
        payload  = _auth_svc.decode_token(token)
        user_id  = int(payload["sub"])
    except Exception:
        raise _credentials_exc
    user = _user_adapter.get_by_id(user_id)
    if user is None or not user.is_active:
        raise _credentials_exc
    return user


async def get_current_user(token: str = Depends(oauth2_scheme)) -> User:
    return _resolve_token(token)


async def require_admin(current_user: User = Depends(get_current_user)) -> User:
    if current_user.role != UserRole.ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin role required",
        )
    return current_user


async def get_user_from_token_param(token: str = Query(..., description="JWT bearer token")) -> User:
    """Used by SSE endpoints that cannot send Authorization headers."""
    return _resolve_token(token)
