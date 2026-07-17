from fastapi import APIRouter, Depends, Query

from api.deps import get_current_user
from domain.entities import User

router = APIRouter()


@router.get(
    "/search",
    summary="Semantic search across the current user's transcripts",
    tags=["db"],
    responses={401: {"description": "Not authenticated"}},
)
async def semantic_search(
    q: str = Query(..., min_length=1),
    n: int = Query(5, ge=1, le=20),
    current_user: User = Depends(get_current_user),
):
    try:
        from application.db_service import DBService
        results = DBService().semantic_search(q, n, user_id=current_user.id)
        return {"query": q, "results": results}
    except RuntimeError as exc:
        return {"query": q, "results": [], "error": str(exc)}


@router.get(
    "/transcriptions",
    summary="List all indexed transcriptions for the current user",
    tags=["db"],
    responses={401: {"description": "Not authenticated"}},
)
async def list_indexed(current_user: User = Depends(get_current_user)):
    from application.db_service import DBService
    return {"transcriptions": DBService().list_transcriptions(user_id=current_user.id)}
