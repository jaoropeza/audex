import asyncio
import collections
import json
import os
import re
import subprocess
import sys
import threading
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

router = APIRouter()
PROJECT_DIR = Path(__file__).parent.parent

# ── Module-level state (single concurrent session) ────────────────────────────
_process: Optional[subprocess.Popen] = None
_active_file: Optional[str] = None          # absolute path
_pid: Optional[int] = None
_log_buffer: collections.deque = collections.deque(maxlen=300)
_log_event = threading.Event()              # set whenever a new line is appended
_file_known = threading.Event()             # set when output path is discovered


def is_recording_running() -> bool:
    return _process is not None and _process.poll() is None


def _drain_stdout(proc: subprocess.Popen):
    global _active_file
    try:
        for raw in proc.stdout:
            line = raw.rstrip("\n")
            _log_buffer.append(line)
            _log_event.set()
            if "Transcript will be saved to:" in line:
                path = line.split(": ", 1)[1].strip()
                _active_file = path
                _file_known.set()
    except Exception:
        pass


# ── Devices ──────────────────────────────────────────────────────────────────

@router.get("/devices")
async def list_devices():
    """Shell out to main.py --list-devices to avoid importing torch in the server."""
    loop = asyncio.get_event_loop()

    def _run():
        try:
            result = subprocess.run(
                [sys.executable, str(PROJECT_DIR / "main.py"), "--list-devices"],
                capture_output=True, text=True, timeout=30,
                cwd=str(PROJECT_DIR),
            )
            return result.stdout
        except Exception as exc:
            return str(exc)

    output = await loop.run_in_executor(None, _run)

    mic_devices, loopback_devices = [], []
    section = None
    for line in output.splitlines():
        if "Input devices" in line or "microphone" in line.lower():
            section = "mic"
        elif "Loopback devices" in line or "speaker" in line.lower():
            section = "loopback"
        m = re.search(r'"([^"]+)"', line)
        if m and section == "mic":
            mic_devices.append(m.group(1))
        elif m and section == "loopback":
            loopback_devices.append({"name": m.group(1)})

    return {"mic": mic_devices, "loopback": loopback_devices}


# ── Start recording ───────────────────────────────────────────────────────────

class StartRequest(BaseModel):
    mode: str                           # "mic" | "loopback" | "merge"
    device: Optional[str] = None        # loopback device hint, or mic device
    mic: Optional[str] = None           # merge mode mic
    model: Optional[str] = None         # None → use saved STT config default
    language: Optional[str] = None      # None → use saved STT config default
    diarize: bool = False
    hf_token: Optional[str] = None
    num_speakers: Optional[int] = None
    output_prefix: str = "transcript"
    save_audio: bool = False
    summarize: bool = False


@router.post("/start")
async def start_recording(req: StartRequest):
    global _process, _active_file, _pid

    if is_recording_running():
        raise HTTPException(status_code=409, detail="Recording already in progress")

    cmd = [sys.executable, str(PROJECT_DIR / "main.py")]

    if req.mode == "mic":
        if not req.device:
            raise HTTPException(status_code=422, detail="device required for mic mode")
        cmd += ["--device", req.device]
    elif req.mode == "loopback":
        cmd.append("--loopback")
        if req.device:
            cmd += ["--device", req.device]
    elif req.mode == "merge":
        if not req.mic:
            raise HTTPException(status_code=422, detail="mic required for merge mode")
        cmd += ["--merge", "--mic", req.mic]
        if req.device:
            cmd += ["--device", req.device]
    else:
        raise HTTPException(status_code=422, detail=f"Unknown mode: {req.mode}")

    from application.config_service import ConfigService
    stt_cfg = ConfigService().get().stt
    model    = req.model    or stt_cfg.model    or "large-v3"
    language = req.language or stt_cfg.language or "es"
    cmd += ["--model", model]
    if language and language != "auto":
        cmd += ["--language", language]
    # Write transcripts into the dedicated transcripts/ subfolder
    transcripts_dir = PROJECT_DIR / "transcripts"
    transcripts_dir.mkdir(parents=True, exist_ok=True)
    output_path = str(transcripts_dir / req.output_prefix)
    cmd += ["--output", output_path]

    if req.diarize:
        cmd.append("--diarize")
        token = req.hf_token or os.environ.get("HF_TOKEN", "")
        if token:
            cmd += ["--hf-token", token]
        if req.num_speakers:
            cmd += ["--num-speakers", str(req.num_speakers)]

    if req.save_audio:
        cmd.append("--save-audio")
    if req.summarize:
        cmd.append("--summarize")

    _active_file = None
    _file_known.clear()
    _log_buffer.clear()

    env = os.environ.copy()
    env["PYTHONUNBUFFERED"] = "1"

    _process = subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1,
        cwd=str(PROJECT_DIR),
        env=env,
    )
    _pid = _process.pid

    threading.Thread(target=_drain_stdout, args=(_process,), daemon=True).start()

    # Wait up to 10 s for main.py to report the output filename
    loop = asyncio.get_event_loop()
    await loop.run_in_executor(None, _file_known.wait, 10.0)

    if not _active_file:
        _process.terminate()
        raise HTTPException(status_code=500, detail="Could not determine output file from main.py")

    filename = Path(_active_file).name
    return {"status": "started", "output_file": filename, "pid": _pid}


# ── Stop recording ────────────────────────────────────────────────────────────

@router.post("/stop")
async def stop_recording():
    global _process

    if not is_recording_running():
        raise HTTPException(status_code=409, detail="No recording in progress")

    loop = asyncio.get_event_loop()

    def _stop():
        # Write a sentinel file instead of CTRL_BREAK_EVENT.
        # The Intel Fortran runtime (bundled with NumPy / ONNX) intercepts
        # CTRL_BREAK and calls TerminateProcess(), bypassing Python's finally blocks.
        stop_file = None
        if _active_file:
            stop_file = Path(_active_file).with_suffix(".stop")
            try:
                stop_file.write_text("stop")
            except Exception:
                stop_file = None

        # Give main.py up to 30 s to finish cleanup (model flush + WAV write)
        try:
            _process.wait(timeout=30)
        except Exception:
            # Timed out — fall back to forceful termination
            try:
                _process.terminate()
                _process.wait(timeout=5)
            except Exception:
                _process.kill()

        # Remove the sentinel if main.py didn't delete it
        if stop_file:
            try:
                stop_file.unlink(missing_ok=True)
            except Exception:
                pass

    await loop.run_in_executor(None, _stop)

    # Index the finished transcript into the vector DB
    if _active_file:
        def _index():
            try:
                from application.db_service import DBService, TRANSCRIPTS_DIR
                fname = Path(_active_file).name
                path  = TRANSCRIPTS_DIR / fname
                if not path.exists():
                    path = Path(_active_file)
                if path.exists():
                    with open(path, "r", encoding="utf-8", errors="ignore") as fh:
                        lines = [ln.rstrip() for ln in fh if ln.strip()]
                    DBService().index(fname, lines)
            except Exception:
                pass
        await loop.run_in_executor(None, _index)

    return {"status": "stopped"}


# ── Status ────────────────────────────────────────────────────────────────────

@router.get("/status")
async def recording_status():
    running = is_recording_running()
    filename = Path(_active_file).name if running and _active_file else None
    return {"running": running, "output_file": filename, "pid": _pid if running else None}


# ── Log SSE ───────────────────────────────────────────────────────────────────

@router.get("/log")
async def stream_log(request: Request):
    already_sent = 0

    async def gen():
        nonlocal already_sent
        while True:
            if await request.is_disconnected():
                break
            snapshot = list(_log_buffer)
            for line in snapshot[already_sent:]:
                already_sent += 1
                yield f"event: line\ndata: {json.dumps({'text': line, 'line_number': already_sent})}\n\n"
            _log_event.clear()
            await asyncio.sleep(0.15)

    return StreamingResponse(
        gen(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
