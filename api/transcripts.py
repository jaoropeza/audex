from __future__ import annotations

import datetime
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import FileResponse
from pydantic import BaseModel

router = APIRouter()

PROJECT_DIR     = Path(__file__).parent.parent
TRANSCRIPTS_DIR = PROJECT_DIR / "transcripts"


def _resolve(filename: str) -> Optional[Path]:
    """Return the absolute path of a transcript, checking transcripts/ then project root."""
    for base in (TRANSCRIPTS_DIR, PROJECT_DIR):
        try:
            target = (base / filename).resolve()
            if (
                target.parent == base.resolve()
                and target.suffix == ".txt"
                and not target.name.endswith("_summary.txt")
                and target.exists()
            ):
                return target
        except Exception:
            pass
    return None


def _is_safe_name(filename: str) -> bool:
    """Reject path traversal and non-.txt names."""
    p = Path(filename)
    return (
        p.name == filename  # no directory separators
        and p.suffix == ".txt"
        and not p.name.endswith("_summary.txt")
    )


def _line_count(path: Path) -> int:
    try:
        with open(path, "r", encoding="utf-8", errors="ignore") as f:
            return sum(1 for line in f if line.strip())
    except OSError:
        return 0


# ── List ─────────────────────────────────────────────────────────────────────

@router.get("")
async def list_transcripts():
    TRANSCRIPTS_DIR.mkdir(parents=True, exist_ok=True)
    files = []

    # Collect tags from DB (best-effort)
    tags_map: dict[str, list[str]] = {}
    summaries_set: set[str] = set()
    try:
        from application.db_service import DBService
        db = DBService()
        for row in db.list_transcriptions():
            tags_map[row["filename"]] = row.get("tags", [])
            if row.get("has_summary"):
                summaries_set.add(row["filename"])
    except Exception:
        pass

    for p in TRANSCRIPTS_DIR.glob("*.txt"):
        if p.name.endswith("_summary.txt"):
            continue
        stat = p.stat()
        files.append({
            "name": p.name,
            "size_bytes": stat.st_size,
            "modified_iso": datetime.datetime.fromtimestamp(stat.st_mtime).isoformat(timespec="seconds"),
            "line_count": _line_count(p),
            "tags": tags_map.get(p.name, []),
            "has_summary": p.name in summaries_set,
        })
    files.sort(key=lambda x: x["modified_iso"], reverse=True)
    return {"files": files}


# ── Get transcript ────────────────────────────────────────────────────────────

@router.get("/{filename}")
async def get_transcript(filename: str):
    if not _is_safe_name(filename):
        raise HTTPException(status_code=400, detail="Invalid filename")
    path = _resolve(filename)
    if path is None:
        raise HTTPException(status_code=404, detail="Transcript not found")
    with open(path, "r", encoding="utf-8", errors="ignore") as f:
        lines = [line.rstrip("\n") for line in f if line.strip()]
    return {"name": filename, "lines": lines}


# ── Delete ────────────────────────────────────────────────────────────────────

@router.delete("/{filename}")
async def delete_transcript(filename: str):
    if not _is_safe_name(filename):
        raise HTTPException(status_code=400, detail="Invalid filename")
    path = _resolve(filename)
    if path is None:
        raise HTTPException(status_code=404, detail="Transcript not found")
    path.unlink()
    summary = path.with_name(path.stem + "_summary.txt")
    if summary.exists():
        summary.unlink()
    try:
        from adapters.db.sqlite_adapter import SQLiteAdapter
        SQLiteAdapter()  # FK cascade deletes summary + tags
    except Exception:
        pass
    return {"deleted": filename}


# ── Search ────────────────────────────────────────────────────────────────────

@router.get("/{filename}/search")
async def search_transcript(filename: str, q: str = Query(..., min_length=1)):
    if not _is_safe_name(filename):
        raise HTTPException(status_code=400, detail="Invalid filename")
    path = _resolve(filename)
    if path is None:
        raise HTTPException(status_code=404, detail="Transcript not found")
    term = q.lower()
    matches = []
    with open(path, "r", encoding="utf-8", errors="ignore") as f:
        for i, line in enumerate(f, start=1):
            stripped = line.rstrip("\n")
            if stripped and term in stripped.lower():
                matches.append({"line_number": i, "text": stripped})
    return {"query": q, "matches": matches}


# ── Tags ──────────────────────────────────────────────────────────────────────

@router.get("/{filename}/tags")
async def get_tags(filename: str):
    if not _is_safe_name(filename):
        raise HTTPException(status_code=400, detail="Invalid filename")
    from application.db_service import DBService
    return {"filename": filename, "tags": DBService().get_tags(filename)}


class TagsBody(BaseModel):
    tags: list[str]


@router.put("/{filename}/tags")
async def set_tags(filename: str, body: TagsBody):
    if not _is_safe_name(filename):
        raise HTTPException(status_code=400, detail="Invalid filename")
    # Auto-upsert transcript record so FK is satisfied
    from application.db_service import DBService, TRANSCRIPTS_DIR as TD
    db = DBService()
    path = _resolve(filename)
    if path is not None:
        line_count = _line_count(path)
        db.index(filename, [])  # upsert metadata row
        from adapters.db.sqlite_adapter import SQLiteAdapter
        SQLiteAdapter().upsert_transcript(filename, line_count)
    db.set_tags(filename, body.tags)
    return {"filename": filename, "tags": db.get_tags(filename)}


@router.get("/tags/all")
async def all_tags():
    from application.db_service import DBService
    return {"tags": DBService().all_distinct_tags()}


# ── Audio ─────────────────────────────────────────────────────────────────────

def _audio_path(filename: str) -> Optional[Path]:
    """Return path to the .wav paired with this transcript, or None if missing."""
    wav_name = Path(filename).stem + ".wav"
    for base in (TRANSCRIPTS_DIR, PROJECT_DIR):
        p = base / wav_name
        if p.exists():
            return p
    return None


@router.get("/{filename}/audio/info")
async def audio_info(filename: str):
    if not _is_safe_name(filename):
        raise HTTPException(status_code=400, detail="Invalid filename")
    path = _audio_path(filename)
    if path is None:
        return {"exists": False}
    stat = path.stat()
    return {"exists": True, "filename": path.name, "size_bytes": stat.st_size}


@router.get("/{filename}/audio")
async def get_audio(filename: str):
    if not _is_safe_name(filename):
        raise HTTPException(status_code=400, detail="Invalid filename")
    path = _audio_path(filename)
    if path is None:
        raise HTTPException(status_code=404, detail="Audio file not found")
    return FileResponse(
        path=str(path),
        media_type="audio/wav",
        filename=path.name,
        headers={"Accept-Ranges": "bytes"},
    )


# ── Summary ───────────────────────────────────────────────────────────────────

@router.get("/{filename}/summary")
async def get_summary(filename: str):
    if not _is_safe_name(filename):
        raise HTTPException(status_code=400, detail="Invalid filename")
    from application.db_service import DBService
    row = DBService().get_summary(filename)
    if not row:
        raise HTTPException(status_code=404, detail="No summary found")
    return row


class SummarizeRequest(BaseModel):
    prompt_template: Optional[str] = None


@router.post("/{filename}/summarize")
async def summarize_transcript(filename: str, body: SummarizeRequest = SummarizeRequest()):
    if not _is_safe_name(filename):
        raise HTTPException(status_code=400, detail="Invalid filename")
    path = _resolve(filename)
    if path is None:
        raise HTTPException(status_code=404, detail="Transcript not found")

    with open(path, "r", encoding="utf-8", errors="ignore") as f:
        transcript_text = f.read().strip()

    if not transcript_text:
        raise HTTPException(status_code=422, detail="Transcript is empty")
    if len(transcript_text.splitlines()) < 3:
        raise HTTPException(status_code=422, detail="Transcript too short to summarize")

    from application.config_service import ConfigService
    from application.summary_service import SummaryService
    from application.db_service import DBService

    cfg = ConfigService().get().summary
    try:
        summary_text = await SummaryService(cfg).summarize(transcript_text, body.prompt_template)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))

    db = DBService()
    # Ensure transcript row exists before saving summary (FK constraint)
    with open(path, "r", encoding="utf-8", errors="ignore") as f:
        all_lines = [ln.rstrip() for ln in f if ln.strip()]
    db.index(filename, all_lines)
    db.save_summary(
        filename,
        summary_text,
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
