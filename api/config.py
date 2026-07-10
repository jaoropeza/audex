from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional

from application.config_service import ConfigService
from application.translation_service import TranslationService
from application.stt_service import STTService
from application.summary_service import SummaryService
from domain.entities import (
    AppSettings, STTConfig, TranslationConfig, SummaryConfig,
    STTProvider, TranslationProvider, SummaryProvider,
)

router = APIRouter()
_svc = ConfigService()

# ── Pydantic schemas (for request/response) ───────────────────────────────────

class STTConfigSchema(BaseModel):
    provider: str = "faster_whisper"
    model:    str = "large-v3"
    language: str = "es"
    api_url:  Optional[str] = None
    api_key:  Optional[str] = None


class TranslationConfigSchema(BaseModel):
    provider:        str           = "anthropic"
    model:           str           = "claude-haiku-4-5-20251001"
    api_url:         Optional[str] = None
    api_key:         Optional[str] = None
    prompt_template: Optional[str] = None


class SummaryConfigSchema(BaseModel):
    provider:        str           = "anthropic"
    model:           str           = "claude-haiku-4-5-20251001"
    api_url:         Optional[str] = None
    api_key:         Optional[str] = None
    prompt_template: Optional[str] = None


class AppSettingsSchema(BaseModel):
    stt:         STTConfigSchema
    translation: TranslationConfigSchema
    summary:     SummaryConfigSchema


def _mask(settings: AppSettings) -> dict:
    d = settings.to_dict()
    if d["stt"].get("api_key"):
        d["stt"]["api_key"] = "***"
    if d["translation"].get("api_key"):
        d["translation"]["api_key"] = "***"
    if d["summary"].get("api_key"):
        d["summary"]["api_key"] = "***"
    return d


def _schema_to_domain(schema: AppSettingsSchema) -> AppSettings:
    current = _svc.get()
    stt_key = schema.stt.api_key
    if stt_key == "***":
        stt_key = current.stt.api_key
    trans_key = schema.translation.api_key
    if trans_key == "***":
        trans_key = current.translation.api_key
    summ_key = schema.summary.api_key
    if summ_key == "***":
        summ_key = current.summary.api_key

    return AppSettings(
        stt=STTConfig(
            provider = STTProvider(schema.stt.provider),
            model    = schema.stt.model,
            language = schema.stt.language,
            api_url  = schema.stt.api_url or None,
            api_key  = stt_key or None,
        ),
        translation=TranslationConfig(
            provider        = TranslationProvider(schema.translation.provider),
            model           = schema.translation.model,
            api_url         = schema.translation.api_url or None,
            api_key         = trans_key or None,
            prompt_template = schema.translation.prompt_template or None,
        ),
        summary=SummaryConfig(
            provider        = SummaryProvider(schema.summary.provider),
            model           = schema.summary.model,
            api_url         = schema.summary.api_url or None,
            api_key         = summ_key or None,
            prompt_template = schema.summary.prompt_template or None,
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


def _trans_schema_to_cfg(schema: TranslationConfigSchema, stored: TranslationConfig) -> TranslationConfig:
    key = stored.api_key if schema.api_key == "***" else (schema.api_key or None)
    return TranslationConfig(
        provider        = TranslationProvider(schema.provider),
        model           = schema.model or stored.model,
        api_url         = schema.api_url or None,
        api_key         = key,
        prompt_template = schema.prompt_template or None,
    )


def _stt_schema_to_cfg(schema: STTConfigSchema, stored: STTConfig) -> STTConfig:
    key = stored.api_key if schema.api_key == "***" else (schema.api_key or None)
    return STTConfig(
        provider = STTProvider(schema.provider),
        model    = schema.model or stored.model,
        language = schema.language or stored.language,
        api_url  = schema.api_url or None,
        api_key  = key,
    )


def _summary_schema_to_cfg(schema: SummaryConfigSchema, stored: SummaryConfig) -> SummaryConfig:
    key = stored.api_key if schema.api_key == "***" else (schema.api_key or None)
    return SummaryConfig(
        provider        = SummaryProvider(schema.provider),
        model           = schema.model or stored.model,
        api_url         = schema.api_url or None,
        api_key         = key,
        prompt_template = schema.prompt_template or None,
    )


@router.post("/config/test/translation")
async def test_translation(body: Optional[TranslationConfigSchema] = None):
    stored = _svc.get()
    cfg = _trans_schema_to_cfg(body, stored.translation) if body else stored.translation
    result = await TranslationService(cfg).test()
    return result


@router.post("/config/test/stt")
async def test_stt(body: Optional[STTConfigSchema] = None):
    stored = _svc.get()
    cfg = _stt_schema_to_cfg(body, stored.stt) if body else stored.stt
    result = await STTService(cfg).test()
    return result


@router.post("/config/test/summary")
async def test_summary(body: Optional[SummaryConfigSchema] = None):
    stored = _svc.get()
    cfg = _summary_schema_to_cfg(body, stored.summary) if body else stored.summary
    result = await SummaryService(cfg).test()
    return result


@router.post("/config/reset")
async def reset_config():
    return _mask(_svc.reset())
