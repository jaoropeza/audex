from __future__ import annotations

import os
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from adapters.db.sqlite_adapter import SQLiteAdapter, _get_db_path
from adapters.db.user_adapter import UserAdapter
from api.deps import get_current_user, require_admin
from application.auth_service import AuthService
from application.config_service import ConfigService
from domain.entities import User, AppSettings

router = APIRouter()
_users    = UserAdapter()
_sqlite   = SQLiteAdapter()
_auth_svc = AuthService()

PROJECT_DIR     = Path(__file__).parent.parent
_default_td     = PROJECT_DIR / "transcripts"
TRANSCRIPTS_DIR = Path(os.environ.get("STT_TRANSCRIPTS_DIR", str(_default_td)))


def _user_out(user: User, transcript_count: int = 0) -> dict:
    return {
        "id":               user.id,
        "username":         user.username,
        "email":            user.email,
        "role":             user.role.value,
        "is_active":        user.is_active,
        "created_at":       user.created_at,
        "transcript_count": transcript_count,
    }


def _dir_size(path: Path) -> int:
    total = 0
    if path.exists():
        for p in path.rglob("*"):
            if p.is_file():
                try:
                    total += p.stat().st_size
                except OSError:
                    pass
    return total


# ── User management ───────────────────────────────────────────────────────────

@router.get(
    "/users",
    summary="List all users with their transcript counts",
    tags=["admin"],
    responses={401: {"description": "Not authenticated"}, 403: {"description": "Admin required"}},
)
async def list_users(_admin: User = Depends(require_admin)):
    users = _users.list_users()
    return [_user_out(u, _users.get_user_transcript_count(u.id)) for u in users]


class CreateUserBody(BaseModel):
    username: str
    password: str
    email:    Optional[str] = None
    role:     str           = "user"


@router.post(
    "/users",
    summary="Create a new user (admin only)",
    tags=["admin"],
    responses={
        401: {"description": "Not authenticated"},
        403: {"description": "Admin required"},
        409: {"description": "Username already exists"},
    },
)
async def create_user(body: CreateUserBody, _admin: User = Depends(require_admin)):
    hashed = _auth_svc.hash_password(body.password)
    try:
        user = _users.create_user(body.username, hashed, role=body.role, email=body.email)
        return _user_out(user, 0)
    except Exception as exc:
        if "UNIQUE" in str(exc):
            raise HTTPException(status_code=409, detail="Username already exists")
        raise HTTPException(status_code=500, detail=str(exc))


class UpdateUserBody(BaseModel):
    role:      Optional[str]  = None
    is_active: Optional[bool] = None


@router.put(
    "/users/{user_id}",
    summary="Update a user's role or active status",
    tags=["admin"],
    responses={
        401: {"description": "Not authenticated"},
        403: {"description": "Admin required"},
        404: {"description": "User not found"},
    },
)
async def update_user(
    user_id: int,
    body: UpdateUserBody,
    _admin: User = Depends(require_admin),
):
    user = _users.update_user(user_id, role=body.role, is_active=body.is_active)
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")
    return _user_out(user, _users.get_user_transcript_count(user.id))


# ── Stats ─────────────────────────────────────────────────────────────────────

@router.get(
    "/stats",
    summary="System statistics",
    tags=["admin"],
    responses={401: {"description": "Not authenticated"}, 403: {"description": "Admin required"}},
)
async def get_stats(_admin: User = Depends(require_admin)):
    users_list   = _users.list_users()
    active_users = sum(1 for u in users_list if u.is_active)

    db_path     = _get_db_path()
    db_size     = db_path.stat().st_size if db_path.exists() else 0
    chroma_dir  = PROJECT_DIR / "db" / "chroma"
    chroma_size = _dir_size(chroma_dir)
    td_size     = _dir_size(TRANSCRIPTS_DIR)

    return {
        "total_users":                len(users_list),
        "active_users":               active_users,
        "total_transcripts":          _sqlite.count_transcriptions(),
        "db_size_bytes":              db_size,
        "chroma_size_bytes":          chroma_size,
        "transcripts_dir_size_bytes": td_size,
    }


# ── Global settings (admin view/edit) ─────────────────────────────────────────

@router.get(
    "/global-settings",
    summary="Get global (default) provider configuration",
    tags=["admin"],
    responses={401: {"description": "Not authenticated"}, 403: {"description": "Admin required"}},
)
async def get_global_settings(_admin: User = Depends(require_admin)):
    settings = ConfigService().get()   # no user_id → global file
    d = settings.to_dict()
    for section in ("stt", "translation", "summary", "embedding"):
        if d.get(section, {}).get("api_key"):
            d[section]["api_key"] = "***"
    return d


class GlobalSettingsBody(BaseModel):
    stt:         dict
    translation: dict
    summary:     dict
    embedding:   dict = {}


@router.put(
    "/global-settings",
    summary="Update global (default) provider configuration",
    tags=["admin"],
    responses={401: {"description": "Not authenticated"}, 403: {"description": "Admin required"}},
)
async def put_global_settings(
    body: GlobalSettingsBody,
    _admin: User = Depends(require_admin),
):
    svc     = ConfigService()
    current = svc.get()

    def _resolve_key(section_dict: dict, current_val: Optional[str]) -> Optional[str]:
        key = section_dict.get("api_key")
        return current_val if key == "***" else (key or None)

    try:
        settings = AppSettings.from_dict({
            "stt":         {**body.stt,         "api_key": _resolve_key(body.stt,         current.stt.api_key)},
            "translation": {**body.translation, "api_key": _resolve_key(body.translation, current.translation.api_key)},
            "summary":     {**body.summary,     "api_key": _resolve_key(body.summary,     current.summary.api_key)},
            "embedding":   body.embedding or {},
        })
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))

    svc.save(settings)
    d = settings.to_dict()
    for section in ("stt", "translation", "summary", "embedding"):
        if d.get(section, {}).get("api_key"):
            d[section]["api_key"] = "***"
    return d
