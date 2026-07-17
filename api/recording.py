import asyncio
import collections
import json
import logging
import os
import re
import subprocess
import sys
import tempfile
import threading
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from api.deps import get_current_user, get_user_from_token_param
from domain.entities import User

router = APIRouter()
logger = logging.getLogger("stt.recording")
PROJECT_DIR     = Path(__file__).parent.parent
_default_td     = PROJECT_DIR / "transcripts"
TRANSCRIPTS_DIR = Path(os.environ.get("STT_TRANSCRIPTS_DIR", str(_default_td)))

# ── Module-level state (single concurrent session) ────────────────────────────
_process:        Optional[subprocess.Popen] = None
_active_file:    Optional[str]              = None   # absolute path
_active_user_id: Optional[int]              = None   # user who started recording
_pid:            Optional[int]              = None
_log_buffer: collections.deque = collections.deque(maxlen=300)
_log_event  = threading.Event()   # set whenever a new line is appended
_file_known = threading.Event()   # set when output path is discovered


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

@router.get(
    "/devices",
    summary="List available audio input devices",
    tags=["recording"],
    responses={401: {"description": "Not authenticated"}},
)
async def list_devices(current_user: User = Depends(get_current_user)):
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
    mode:           str
    device:         Optional[str] = None
    mic:            Optional[str] = None
    model:          Optional[str] = None
    language:       Optional[str] = None
    diarize:        bool          = False
    hf_token:       Optional[str] = None
    num_speakers:   Optional[int] = None
    output_prefix:  str           = "transcript"
    save_audio:     bool          = False
    summarize:      bool          = False


@router.post(
    "/start",
    summary="Start a recording session",
    tags=["recording"],
    responses={
        401: {"description": "Not authenticated"},
        409: {"description": "Recording already in progress"},
        422: {"description": "Invalid request parameters"},
    },
)
async def start_recording(req: StartRequest, current_user: User = Depends(get_current_user)):
    global _process, _active_file, _active_user_id, _pid

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
    stt_cfg  = ConfigService(current_user.id).get().stt
    model    = req.model    or stt_cfg.model    or "large-v3"
    language = req.language or stt_cfg.language or "es"
    cmd += ["--model", model]
    if language and language != "auto":
        cmd += ["--language", language]

    # Write transcripts into the user-specific subfolder
    user_dir = TRANSCRIPTS_DIR / str(current_user.id)
    user_dir.mkdir(parents=True, exist_ok=True)
    output_path = str(user_dir / req.output_prefix)
    cmd += ["--output", output_path]

    if req.diarize:
        cmd.append("--diarize")
        token = req.hf_token or os.environ.get("HF_TOKEN", "")
        if token:
            cmd += ["--hf-token", token]
        if req.num_speakers:
            cmd += ["--num-speakers", str(req.num_speakers)]

        # Inject the user's named speaker profiles so they are resolved by name
        # at recording time rather than appearing as anonymous SPEAKER_N labels.
        try:
            from adapters.db.speaker_adapter import SpeakerAdapter
            profiles = SpeakerAdapter().get_embeddings_for_user(current_user.id)
            if profiles:
                tmp = tempfile.NamedTemporaryFile(
                    mode="w", suffix=".json", delete=False, encoding="utf-8"
                )
                json.dump({"profiles": profiles}, tmp)
                tmp.close()
                cmd += ["--speaker-profiles-json", tmp.name]
                # Clean up after main.py has had time to read it
                def _cleanup(path):
                    import time; time.sleep(10)
                    try: os.unlink(path)
                    except OSError: pass
                threading.Thread(target=_cleanup, args=(tmp.name,), daemon=True).start()
        except Exception:
            pass

    if req.save_audio:
        cmd.append("--save-audio")
    if req.summarize:
        cmd.append("--summarize")

    logger.info("Starting recording: user=%d mode=%s model=%s", current_user.id, req.mode, model)
    _active_file    = None
    _active_user_id = current_user.id
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

    loop = asyncio.get_event_loop()
    await loop.run_in_executor(None, _file_known.wait, 10.0)

    if not _active_file:
        _process.terminate()
        raise HTTPException(status_code=500, detail="Could not determine output file from main.py")

    filename = Path(_active_file).name
    logger.info("Recording started: file=%s pid=%d user=%d", filename, _pid, current_user.id)
    return {"status": "started", "output_file": filename, "pid": _pid}


# ── Stop recording ────────────────────────────────────────────────────────────

@router.post(
    "/stop",
    summary="Stop the current recording session and index the transcript",
    tags=["recording"],
    responses={
        401: {"description": "Not authenticated"},
        409: {"description": "No recording in progress"},
    },
)
async def stop_recording(current_user: User = Depends(get_current_user)):
    global _process, _active_user_id

    if not is_recording_running():
        raise HTTPException(status_code=409, detail="No recording in progress")

    loop = asyncio.get_event_loop()

    def _stop():
        stop_file = None
        if _active_file:
            stop_file = Path(_active_file).with_suffix(".stop")
            try:
                stop_file.write_text("stop")
            except Exception:
                stop_file = None

        try:
            _process.wait(timeout=30)
        except Exception:
            try:
                _process.terminate()
                _process.wait(timeout=5)
            except Exception:
                _process.kill()

        if stop_file:
            try:
                stop_file.unlink(missing_ok=True)
            except Exception:
                pass

    await loop.run_in_executor(None, _stop)

    # Index the finished transcript into the vector DB under the recording user
    recorded_user_id = _active_user_id
    if _active_file:
        active_file_snapshot = _active_file

        def _index():
            try:
                from application.db_service import DBService
                fname = Path(active_file_snapshot).name
                path  = Path(active_file_snapshot)
                if not path.exists():
                    path = TRANSCRIPTS_DIR / str(recorded_user_id) / fname if recorded_user_id else TRANSCRIPTS_DIR / fname
                if path.exists():
                    content = path.read_text(encoding="utf-8", errors="ignore")
                    lines   = [ln.rstrip() for ln in content.splitlines() if ln.strip()]
                    DBService().index(fname, lines, user_id=recorded_user_id)
            except Exception:
                pass

        await loop.run_in_executor(None, _index)

    logger.info("Recording stopped: file=%s user=%s", _active_file, recorded_user_id)
    _active_user_id = None
    return {"status": "stopped"}


# ── Status ────────────────────────────────────────────────────────────────────

@router.get(
    "/status",
    summary="Get current recording session status",
    tags=["recording"],
    responses={401: {"description": "Not authenticated"}},
)
async def recording_status(current_user: User = Depends(get_current_user)):
    running  = is_recording_running()
    filename = Path(_active_file).name if running and _active_file else None
    return {"running": running, "output_file": filename, "pid": _pid if running else None}


# ── Log SSE ───────────────────────────────────────────────────────────────────

@router.get(
    "/log",
    summary="Stream recording process log lines via SSE",
    description="Use ?token=<jwt> since EventSource cannot send Authorization headers.",
    tags=["recording"],
    responses={401: {"description": "Not authenticated"}},
)
async def stream_log(
    request: Request,
    current_user: User = Depends(get_user_from_token_param),
):
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
