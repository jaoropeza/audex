from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from pydantic import BaseModel

from api.deps import get_current_user
from domain.entities import User

router = APIRouter()

_MAX_WAV_BYTES = 10 * 1024 * 1024  # 10 MB


# ── List ─────────────────────────────────────────────────────────────────────

@router.get(
    "",
    summary="List speaker profiles for the current user",
    tags=["speakers"],
    responses={401: {"description": "Not authenticated"}},
)
async def list_profiles(current_user: User = Depends(get_current_user)):
    from adapters.db.speaker_adapter import SpeakerAdapter
    return SpeakerAdapter().list(current_user.id)


# ── Create / update ───────────────────────────────────────────────────────────

@router.post(
    "",
    summary="Upload a WAV sample to create or update a speaker profile",
    description=(
        "Upload a short (5–30 s) WAV file of the speaker.\n\n"
        "The server extracts a speaker embedding using pyannote/embedding and "
        "stores it in the database.  Requires `HF_TOKEN` to be set on the server.\n\n"
        "If a profile with the same name already exists for this user it is replaced."
    ),
    tags=["speakers"],
    responses={
        401: {"description": "Not authenticated"},
        503: {"description": "HF_TOKEN not configured on the server"},
        422: {"description": "File is not a valid WAV or exceeds 10 MB"},
    },
)
async def create_profile(
    name: str,
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
):
    from application.speaker_service import SpeakerService
    from adapters.db.speaker_adapter import SpeakerAdapter
    import asyncio

    svc = SpeakerService()
    if not svc.available:
        raise HTTPException(
            status_code=503,
            detail="HF_TOKEN is not set on the server — cannot extract speaker embeddings",
        )

    if not file.filename or not file.filename.lower().endswith(".wav"):
        raise HTTPException(status_code=422, detail="Only .wav files are accepted")

    wav_bytes = await file.read()
    if len(wav_bytes) > _MAX_WAV_BYTES:
        raise HTTPException(status_code=422, detail="File exceeds 10 MB limit")

    try:
        loop = asyncio.get_event_loop()
        embedding = await loop.run_in_executor(None, svc.extract_embedding, wav_bytes)
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=422, detail=f"Could not read audio: {exc}")

    profile = SpeakerAdapter().upsert(current_user.id, name.strip(), embedding)
    return profile


# ── Delete ────────────────────────────────────────────────────────────────────

@router.delete(
    "/{name}",
    summary="Delete a speaker profile",
    tags=["speakers"],
    responses={
        401: {"description": "Not authenticated"},
        404: {"description": "Profile not found"},
    },
)
async def delete_profile(name: str, current_user: User = Depends(get_current_user)):
    from adapters.db.speaker_adapter import SpeakerAdapter
    deleted = SpeakerAdapter().delete(current_user.id, name)
    if not deleted:
        raise HTTPException(status_code=404, detail="Speaker profile not found")
    return {"deleted": name}
