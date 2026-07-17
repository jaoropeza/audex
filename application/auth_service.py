from __future__ import annotations

import os
from datetime import datetime, timedelta
from typing import Optional

import bcrypt
from jose import JWTError, jwt

from domain.entities import User

SECRET_KEY           = os.environ.get("STT_SECRET_KEY", "change-me-in-production-please")
ALGORITHM            = "HS256"
TOKEN_EXPIRE_MINUTES = 60 * 24 * 7  # 1 week


class AuthService:
    def hash_password(self, password: str) -> str:
        return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")

    def verify_password(self, plain: str, hashed: str) -> bool:
        try:
            return bcrypt.checkpw(plain.encode("utf-8"), hashed.encode("utf-8"))
        except Exception:
            return False

    def create_token(self, user: User, expires_minutes: Optional[int] = None) -> str:
        minutes = expires_minutes if expires_minutes is not None else TOKEN_EXPIRE_MINUTES
        payload = {
            "sub":      str(user.id),
            "username": user.username,
            "role":     user.role.value,
            "exp":      datetime.utcnow() + timedelta(minutes=minutes),
        }
        return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)

    def decode_token(self, token: str) -> dict:
        """Decode and verify a JWT. Raises JWTError on failure."""
        return jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
