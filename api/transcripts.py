from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query
from fastapi.responses import FileResponse
from pydantic import BaseModel

from api.deps import get_current_user
from domain.entities import User

router = APIRouter()
logger = logging.getLogger("stt.transcripts")

PROJECT_DIR     = Path(__file__).parent.parent
_default_td     = PROJECT_DIR / "transcripts"
TRANSCRIPTS_DIR = Path(os.environ.get("STT_TRANSCRIPTS_DIR", str(_default_td)))


def _is_safe_name(filename: str) -> bool:
    p = Path(filename)
    return (
        p.name == filename
        and p.suffix == ".txt"
        and not p.name.endswith("_summary.txt")
    )


def _user_dir(user_id: int) -> Path:
    d = TRANSCRIPTS_DIR / str(user_id)
    d.mkdir(parents=True, exist_ok=True)
    return d


def _audio_path(filename: str, user_id: int) -> Optional[Path]:
    wav_name = Path(filename).stem + ".wav"
    for base in (_user_dir(user_id), TRANSCRIPTS_DIR, PROJECT_DIR):
        p = base / wav_name
        if p.exists():
            return p
    return None


# ── List ─────────────────────────────────────────────────────────────────────

@router.get(
    "",
    summary="List all transcripts for the current user",
    description="Returns transcript metadata (no content). Includes tags and summary flag.",
    tags=["transcripts"],
    responses={401: {"description": "Not authenticated"}},
)
async def list_transcripts(current_user: User = Depends(get_current_user)):
    from application.db_service import DBService
    rows = DBService().list_transcriptions(user_id=current_user.id)
    files = []
    user_subdir = TRANSCRIPTS_DIR / str(current_user.id)
    for r in rows:
        fname = r["filename"]
        if not _is_safe_name(fname):
            continue
        # Resolve file size from disk; fall back to 0 if file not found
        size_bytes = 0
        for base in (user_subdir, TRANSCRIPTS_DIR):
            p = base / fname
            try:
                size_bytes = p.stat().st_size
                break
            except OSError:
                pass
        files.append({
            "name": fname,
            "modified_iso": r.get("indexed_at") or r.get("created_at", ""),
            "size_bytes": size_bytes,
            "line_count": r.get("line_count", 0),
            "has_summary": bool(r.get("has_summary", 0)),
            "tags": r.get("tags") or [],
        })
    return {"files": files}


# ── Get transcript ────────────────────────────────────────────────────────────

@router.get(
    "/{filename}",
    summary="Get transcript content (lines)",
    tags=["transcripts"],
    responses={401: {"description": "Not authenticated"}, 404: {"description": "Transcript not found"}},
)
async def get_transcript(filename: str, current_user: User = Depends(get_current_user)):
    if not _is_safe_name(filename):
        logger.debug("Rejected unsafe filename=%r user=%d", filename, current_user.id)
        raise HTTPException(status_code=400, detail="Invalid filename")
    from application.db_service import DBService
    content = DBService().get_content(filename, user_id=current_user.id)
    if content is None:
        logger.debug("Transcript not found: filename=%r user=%d", filename, current_user.id)
        raise HTTPException(status_code=404, detail="Transcript not found")
    lines = [ln.rstrip("\n") for ln in content.splitlines() if ln.strip()]
    logger.debug("Served transcript filename=%r lines=%d user=%d", filename, len(lines), current_user.id)
    return {"name": filename, "lines": lines}


# ── Delete ────────────────────────────────────────────────────────────────────

@router.delete(
    "/{filename}",
    summary="Delete a transcript",
    tags=["transcripts"],
    responses={401: {"description": "Not authenticated"}, 404: {"description": "Transcript not found"}},
)
async def delete_transcript(filename: str, current_user: User = Depends(get_current_user)):
    if not _is_safe_name(filename):
        raise HTTPException(status_code=400, detail="Invalid filename")
    from adapters.db.sqlite_adapter import SQLiteAdapter
    db = SQLiteAdapter()
    deleted = db.delete_transcript(filename, user_id=current_user.id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Transcript not found")
    # Best-effort file removal
    for base in (_user_dir(current_user.id), TRANSCRIPTS_DIR):
        p = base / filename
        if p.exists():
            try:
                p.unlink()
            except OSError:
                pass
    return {"deleted": filename}


# ── Search ────────────────────────────────────────────────────────────────────

@router.get(
    "/{filename}/search",
    summary="Search within a transcript",
    tags=["transcripts"],
    responses={401: {"description": "Not authenticated"}, 404: {"description": "Transcript not found"}},
)
async def search_transcript(
    filename: str,
    q: str = Query(..., min_length=1),
    current_user: User = Depends(get_current_user),
):
    if not _is_safe_name(filename):
        raise HTTPException(status_code=400, detail="Invalid filename")
    from application.db_service import DBService
    content = DBService().get_content(filename, user_id=current_user.id)
    if content is None:
        raise HTTPException(status_code=404, detail="Transcript not found")
    term = q.lower()
    matches = [
        {"line_number": i, "text": ln.rstrip()}
        for i, ln in enumerate(content.splitlines(), start=1)
        if ln.strip() and term in ln.lower()
    ]
    return {"query": q, "matches": matches}


# ── Tags ──────────────────────────────────────────────────────────────────────

@router.get(
    "/{filename}/tags",
    summary="Get tags for a transcript",
    tags=["transcripts"],
)
async def get_tags(filename: str, current_user: User = Depends(get_current_user)):
    if not _is_safe_name(filename):
        raise HTTPException(status_code=400, detail="Invalid filename")
    from application.db_service import DBService
    return {"filename": filename, "tags": DBService().get_tags(filename, user_id=current_user.id)}


class TagsBody(BaseModel):
    tags: list[str]


@router.put(
    "/{filename}/tags",
    summary="Set tags for a transcript",
    tags=["transcripts"],
)
async def set_tags(
    filename: str,
    body: TagsBody,
    current_user: User = Depends(get_current_user),
):
    if not _is_safe_name(filename):
        raise HTTPException(status_code=400, detail="Invalid filename")
    from application.db_service import DBService
    db = DBService()
    db.set_tags(filename, body.tags, user_id=current_user.id)
    return {"filename": filename, "tags": db.get_tags(filename, user_id=current_user.id)}


@router.get(
    "/tags/all",
    summary="List all distinct tags for the current user",
    tags=["transcripts"],
)
async def all_tags(current_user: User = Depends(get_current_user)):
    from application.db_service import DBService
    return {"tags": DBService().all_distinct_tags(user_id=current_user.id)}


# ── Audio ─────────────────────────────────────────────────────────────────────

@router.get(
    "/{filename}/audio/info",
    summary="Check if an audio file exists for this transcript",
    tags=["transcripts"],
)
async def audio_info(filename: str, current_user: User = Depends(get_current_user)):
    if not _is_safe_name(filename):
        raise HTTPException(status_code=400, detail="Invalid filename")
    path = _audio_path(filename, current_user.id)
    if path is None:
        return {"exists": False}
    return {"exists": True, "filename": path.name, "size_bytes": path.stat().st_size}


@router.get(
    "/{filename}/audio",
    summary="Download or stream the audio paired with a transcript",
    tags=["transcripts"],
    responses={404: {"description": "Audio file not found"}},
)
async def get_audio(filename: str, current_user: User = Depends(get_current_user)):
    if not _is_safe_name(filename):
        raise HTTPException(status_code=400, detail="Invalid filename")
    path = _audio_path(filename, current_user.id)
    if path is None:
        raise HTTPException(status_code=404, detail="Audio file not found")
    return FileResponse(
        path=str(path),
        media_type="audio/wav",
        filename=path.name,
        headers={"Accept-Ranges": "bytes"},
    )


# ── Summary ───────────────────────────────────────────────────────────────────

@router.get(
    "/{filename}/summary",
    summary="Get the summary for a transcript",
    tags=["transcripts"],
    responses={404: {"description": "No summary found"}},
)
async def get_summary(filename: str, current_user: User = Depends(get_current_user)):
    if not _is_safe_name(filename):
        raise HTTPException(status_code=400, detail="Invalid filename")
    from application.db_service import DBService
    row = DBService().get_summary(filename, user_id=current_user.id)
    if not row:
        raise HTTPException(status_code=404, detail="No summary found")
    return row


class SummarizeRequest(BaseModel):
    prompt_template: Optional[str] = None


@router.post(
    "/{filename}/summarize",
    summary="Generate (or regenerate) a summary for a transcript",
    tags=["transcripts"],
    responses={
        422: {"description": "Transcript is empty or too short"},
        500: {"description": "Summarization provider error"},
    },
)
async def summarize_transcript(
    filename: str,
    body: SummarizeRequest = SummarizeRequest(),
    current_user: User = Depends(get_current_user),
):
    if not _is_safe_name(filename):
        raise HTTPException(status_code=400, detail="Invalid filename")

    from application.db_service import DBService
    db = DBService()
    content = db.get_content(filename, user_id=current_user.id)

    # Fallback: try reading from file (for legacy transcripts not yet in DB)
    if content is None:
        for base in (_user_dir(current_user.id), TRANSCRIPTS_DIR, PROJECT_DIR):
            p = base / filename
            if p.exists() and p.suffix == ".txt":
                content = p.read_text(encoding="utf-8", errors="ignore")
                break

    if not content or not content.strip():
        raise HTTPException(status_code=422, detail="Transcript is empty")
    if len(content.splitlines()) < 3:
        raise HTTPException(status_code=422, detail="Transcript too short to summarize")

    from application.config_service import ConfigService
    from application.summary_service import SummaryService

    cfg = ConfigService(current_user.id).get().summary
    try:
        summary_text = await SummaryService(cfg).summarize(content.strip(), body.prompt_template)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))

    all_lines = [ln.rstrip() for ln in content.splitlines() if ln.strip()]
    db.index(filename, all_lines, user_id=current_user.id)
    db.save_summary(
        filename,
        summary_text,
        user_id=current_user.id,
        provider=cfg.provider.value,
        model=cfg.model,
        prompt_used=body.prompt_template or cfg.prompt_template,
    )

    return {
        "filename": filename,
        "summary": summary_text,
        "provider": cfg.provider.value,
        "model": cfg.model,
    }
