import os
from pathlib import Path
from fastapi import APIRouter, HTTPException, Query

router = APIRouter()
PROJECT_DIR = Path(__file__).parent.parent


def _is_safe(filename: str) -> bool:
    """Reject path traversal and non-transcript files."""
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
    summary = path.with_name(path.stem + "_summary.txt")
    if summary.exists():
        summary.unlink()
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
