import asyncio
import json
from pathlib import Path
from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.responses import StreamingResponse

router = APIRouter()
PROJECT_DIR     = Path(__file__).parent.parent
TRANSCRIPTS_DIR = PROJECT_DIR / "transcripts"


def _resolve(filename: str) -> Path:
    """Return path in transcripts/ if it exists, else fall back to project root."""
    p = TRANSCRIPTS_DIR / filename
    if p.exists():
        return p
    return PROJECT_DIR / filename


def _is_safe(filename: str) -> bool:
    p = Path(filename)
    return p.name == filename and p.suffix == ".txt"


@router.get("/{filename}")
async def stream_transcript(
    filename: str,
    request: Request,
    from_line: int = Query(default=0, ge=0),
):
    if not _is_safe(filename):
        raise HTTPException(status_code=400, detail="Invalid filename")

    filepath = _resolve(filename)

    async def event_generator():
        # Wait up to 10 s for the file to appear (model loading delay)
        for _ in range(100):
            if filepath.exists():
                break
            await asyncio.sleep(0.1)

        if not filepath.exists():
            yield f"event: error\ndata: {json.dumps({'message': 'File not found'})}\n\n"
            return

        line_number = 0
        pos = 0

        # ── Phase 1: catch-up ─────────────────────────────────────────────
        with open(filepath, "r", encoding="utf-8", errors="ignore") as f:
            for raw in f:
                stripped = raw.rstrip("\n")
                if not stripped:
                    continue
                line_number += 1
                if line_number <= from_line:
                    continue
                payload = json.dumps({"text": stripped, "line_number": line_number})
                yield f"event: line\nid: {line_number}\ndata: {payload}\n\n"
            pos = f.tell()

        # ── Phase 2: tail ─────────────────────────────────────────────────
        ping_ticks = 0
        stable_ticks = 0

        while True:
            if await request.is_disconnected():
                break

            try:
                current_size = filepath.stat().st_size
            except FileNotFoundError:
                await asyncio.sleep(0.3)
                continue

            if current_size > pos:
                stable_ticks = 0
                with open(filepath, "r", encoding="utf-8", errors="ignore") as f:
                    f.seek(pos)
                    new_text = f.read()
                    pos = f.tell()
                for raw in new_text.splitlines():
                    stripped = raw.strip()
                    if stripped:
                        line_number += 1
                        payload = json.dumps({"text": stripped, "line_number": line_number})
                        yield f"event: line\nid: {line_number}\ndata: {payload}\n\n"
            else:
                stable_ticks += 1

            ping_ticks += 1
            if ping_ticks >= 75:   # 75 × 200 ms = 15 s
                yield "event: ping\ndata: {}\n\n"
                ping_ticks = 0

            # EOF: file has been stable for 3 s and recording is no longer running
            if stable_ticks >= 15:
                from api.recording import is_recording_running
                if not is_recording_running():
                    payload = json.dumps({"total_lines": line_number})
                    yield f"event: eof\ndata: {payload}\n\n"
                    break

            await asyncio.sleep(0.2)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
            "Connection": "keep-alive",
        },
    )
