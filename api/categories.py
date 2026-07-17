from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from adapters.db.category_adapter import CategoryAdapter
from adapters.db.sqlite_adapter import SQLiteAdapter
from api.deps import get_current_user
from domain.entities import User

router = APIRouter()
_cat  = CategoryAdapter()
_db   = SQLiteAdapter()


class CategoryIn(BaseModel):
    name:        str
    description: Optional[str] = None
    color:       str            = "#6366f1"


class CategoryIds(BaseModel):
    category_ids: list[int]


def _cat_out(cat) -> dict:
    return {
        "id":          cat.id,
        "user_id":     cat.user_id,
        "name":        cat.name,
        "description": cat.description,
        "color":       cat.color,
        "created_at":  cat.created_at,
    }


# ── Category CRUD ─────────────────────────────────────────────────────────────

@router.get(
    "/categories",
    summary="List all categories for the current user",
    tags=["categories"],
    responses={401: {"description": "Not authenticated"}},
)
async def list_categories(current_user: User = Depends(get_current_user)):
    return [_cat_out(c) for c in _cat.list(current_user.id)]


@router.post(
    "/categories",
    summary="Create a new category",
    tags=["categories"],
    responses={
        401: {"description": "Not authenticated"},
        409: {"description": "Category name already exists"},
    },
)
async def create_category(body: CategoryIn, current_user: User = Depends(get_current_user)):
    try:
        cat = _cat.create(current_user.id, body.name, body.color, body.description)
        return _cat_out(cat)
    except Exception as exc:
        if "UNIQUE" in str(exc):
            raise HTTPException(status_code=409, detail=f"Category '{body.name}' already exists")
        raise HTTPException(status_code=500, detail=str(exc))


@router.put(
    "/categories/{category_id}",
    summary="Update a category",
    tags=["categories"],
    responses={
        401: {"description": "Not authenticated"},
        404: {"description": "Category not found"},
    },
)
async def update_category(
    category_id: int,
    body: CategoryIn,
    current_user: User = Depends(get_current_user),
):
    cat = _cat.update(category_id, current_user.id,
                      name=body.name, description=body.description, color=body.color)
    if cat is None:
        raise HTTPException(status_code=404, detail="Category not found")
    return _cat_out(cat)


@router.delete(
    "/categories/{category_id}",
    summary="Delete a category",
    tags=["categories"],
    responses={
        401: {"description": "Not authenticated"},
        404: {"description": "Category not found"},
    },
)
async def delete_category(category_id: int, current_user: User = Depends(get_current_user)):
    deleted = _cat.delete(category_id, current_user.id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Category not found")
    return {"deleted": category_id}


# ── Transcript–category assignment ────────────────────────────────────────────

@router.get(
    "/transcripts/{filename}/categories",
    summary="Get categories assigned to a transcript",
    tags=["categories"],
    responses={
        401: {"description": "Not authenticated"},
        404: {"description": "Transcript not found"},
    },
)
async def get_transcript_categories(filename: str, current_user: User = Depends(get_current_user)):
    tid = _db.get_transcript_id(filename, user_id=current_user.id)
    if tid is None:
        raise HTTPException(status_code=404, detail="Transcript not found")
    cats = _cat.get_transcript_categories(tid, current_user.id)
    return [_cat_out(c) for c in cats]


@router.put(
    "/transcripts/{filename}/categories",
    summary="Assign categories to a transcript",
    tags=["categories"],
    responses={
        401: {"description": "Not authenticated"},
        404: {"description": "Transcript not found"},
    },
)
async def set_transcript_categories(
    filename: str,
    body: CategoryIds,
    current_user: User = Depends(get_current_user),
):
    tid = _db.get_transcript_id(filename, user_id=current_user.id)
    if tid is None:
        raise HTTPException(status_code=404, detail="Transcript not found")
    _cat.set_transcript_categories(tid, current_user.id, body.category_ids)
    cats = _cat.get_transcript_categories(tid, current_user.id)
    return [_cat_out(c) for c in cats]
