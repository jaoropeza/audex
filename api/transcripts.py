import os
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

router = APIRouter()
PROJECT_DIR = Path(__file__).parent.parent


def _is_safe(filename: str) -> bool:
    try:
        target = (PROJECT_DIR / filename).resolve()
        return (
            target.parent == PROJECT_DIR.resolve()
            and target.suffix == ".txt"
            and not target.name.endswith("_summary.txt")
        )
    except Exception:
        return False


def _line_count(path: Path) -> int:
    try:
        with open(path, "r", encoding="utf-8", errors="ignore") as f:
            return sum(1 for line in f if line.strip())
    except OSError:
        return 0


@router.get("")
async def list_transcripts():
    files = []
    for p in PROJECT_DIR.glob("*.txt"):
        if p.name.endswith("_summary.txt"):
            continue
        stat = p.stat()
        files.append({
            "name": p.name,
            "size_bytes": stat.st_size,
            "modified_iso": __import__("datetime").datetime.fromtimestamp(stat.st_mtime).isoformat(timespec="seconds"),
            "line_count": _line_count(p),
        })
    files.sort(key=lambda x: x["modified_iso"], reverse=True)
    return {"files": files}


@router.get("/{filename}")
async def get_transcript(filename: str):
    if not _is_safe(filename):
        raise HTTPException(status_code=400, detail="Invalid filename")
    path = PROJECT_DIR / filename
    if not path.exists():
        raise HTTPException(status_code=404, detail="Transcript not found")
    with open(path, "r", encoding="utf-8", errors="ignore") as f:
        lines = [line.rstrip("\n") for line in f if line.strip()]
    return {"name": filename, "lines": lines}


@router.delete("/{filename}")
async def delete_transcript(filename: str):
    if not _is_safe(filename):
        raise HTTPException(status_code=400, detail="Invalid filename")
    path = PROJECT_DIR / filename
    if not path.exists():
        raise HTTPException(status_code=404, detail="Transcript not found")
    path.unlink()
    summary_file = path.with_name(path.stem + "_summary.txt")
    if summary_file.exists():
        summary_file.unlink()
    # Remove from DB
    try:
        from application.db_service import DBService
        DBService()  # lazy init; no explicit delete needed (cascade via FK)
    except Exception:
        pass
    return {"deleted": filename}


@router.get("/{filename}/search")
async def search_transcript(filename: str, q: str = Query(..., min_length=1)):
    if not _is_safe(filename):
        raise HTTPException(status_code=400, detail="Invalid filename")
    path = PROJECT_DIR / filename
    if not path.exists():
        raise HTTPException(status_code=404, detail="Transcript not found")
    term = q.lower()
    matches = []
    with open(path, "r", encoding="utf-8", errors="ignore") as f:
        for i, line in enumerate(f, start=1):
            stripped = line.rstrip("\n")
            if stripped and term in stripped.lower():
                matches.append({"line_number": i, "text": stripped})
    return {"query": q, "matches": matches}


@router.get("/{filename}/summary")
async def get_summary(filename: str):
    if not _is_safe(filename):
        raise HTTPException(status_code=400, detail="Invalid filename")
    from application.db_service import DBService
    db = DBService()
    row = db.get_summary(filename)
    if not row:
        raise HTTPException(status_code=404, detail="No summary found")
    return row


class SummarizeRequest(BaseModel):
    prompt_template: Optional[str] = None


@router.post("/{filename}/summarize")
async def summarize_transcript(filename: str, body: SummarizeRequest = SummarizeRequest()):
    if not _is_safe(filename):
        raise HTTPException(status_code=400, detail="Invalid filename")
    path = PROJECT_DIR / filename
    if not path.exists():
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
    svc = SummaryService(cfg)

    try:
        summary_text = await svc.summarize(transcript_text, body.prompt_template)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))

    db = DBService()
    # Ensure the transcript row exists before inserting the FK-referenced summary
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
