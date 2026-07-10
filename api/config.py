from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional

from application.config_service import ConfigService
from application.translation_service import TranslationService
from application.stt_service import STTService
from domain.entities import AppSettings, STTConfig, TranslationConfig, STTProvider, TranslationProvider

router = APIRouter()
_svc = ConfigService()

# ── Pydantic schemas (for request/response) ───────────────────────────────────

class STTConfigSchema(BaseModel):
    provider: str = "faster_whisper"
    model:    str = "small"
    language: str = "en"
    api_url:  Optional[str] = None
    api_key:  Optional[str] = None  # incoming: real key; outgoing: "***" if set


class TranslationConfigSchema(BaseModel):
    provider: str = "anthropic"
    model:    str = "claude-haiku-4-5-20251001"
    api_url:  Optional[str] = None
    api_key:  Optional[str] = None


class AppSettingsSchema(BaseModel):
    stt:         STTConfigSchema
    translation: TranslationConfigSchema


def _mask(settings: AppSettings) -> dict:
    d = settings.to_dict()
    if d["stt"].get("api_key"):
        d["stt"]["api_key"] = "***"
    if d["translation"].get("api_key"):
        d["translation"]["api_key"] = "***"
    return d


def _schema_to_domain(schema: AppSettingsSchema) -> AppSettings:
    current = _svc.get()
    # If the frontend sends "***" back, keep the stored key
    stt_key = schema.stt.api_key
    if stt_key == "***":
        stt_key = current.stt.api_key
    trans_key = schema.translation.api_key
    if trans_key == "***":
        trans_key = current.translation.api_key

    return AppSettings(
        stt=STTConfig(
            provider = STTProvider(schema.stt.provider),
            model    = schema.stt.model,
            language = schema.stt.language,
            api_url  = schema.stt.api_url or None,
            api_key  = stt_key or None,
        ),
        translation=TranslationConfig(
            provider = TranslationProvider(schema.translation.provider),
            model    = schema.translation.model,
            api_url  = schema.translation.api_url or None,
            api_key  = trans_key or None,
        ),
    )


# ── Routes ────────────────────────────────────────────────────────────────────

@router.get("/config")
async def get_config():
    return _mask(_svc.get())


@router.put("/config")
async def put_config(body: AppSettingsSchema):
    try:
        settings = _schema_to_domain(body)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    _svc.save(settings)
    return _mask(settings)


@router.post("/config/test/translation")
async def test_translation():
    cfg = _svc.get()
    result = await TranslationService(cfg.translation).test()
    return result


@router.post("/config/test/stt")
async def test_stt():
    cfg = _svc.get()
    result = await STTService(cfg.stt).test()
    return result


@router.post("/config/reset")
async def reset_config():
    return _mask(_svc.reset())
