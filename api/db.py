from fastapi import APIRouter, Query

router = APIRouter()


@router.get("/search")
async def semantic_search(q: str = Query(..., min_length=1), n: int = Query(5, ge=1, le=20)):
    try:
        from application.db_service import DBService
        results = DBService().semantic_search(q, n)
        return {"query": q, "results": results}
    except RuntimeError as exc:
        return {"query": q, "results": [], "error": str(exc)}


@router.get("/transcriptions")
async def list_indexed():
    from application.db_service import DBService
    return {"transcriptions": DBService().list_transcriptions()}
