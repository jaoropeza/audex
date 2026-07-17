from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from typing import Optional

from application.config_service import ConfigService
from application.translation_service import TranslationService
from application.stt_service import STTService
from application.summary_service import SummaryService
from api.deps import get_current_user
from domain.entities import (
    AppSettings, STTConfig, TranslationConfig, SummaryConfig,
    STTProvider, TranslationProvider, SummaryProvider, User,
)

router = APIRouter()

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


def _schema_to_domain(schema: AppSettingsSchema, current: AppSettings) -> AppSettings:
    stt_key   = current.stt.api_key   if schema.stt.api_key   == "***" else (schema.stt.api_key   or None)
    trans_key = current.translation.api_key if schema.translation.api_key == "***" else (schema.translation.api_key or None)
    summ_key  = current.summary.api_key if schema.summary.api_key == "***" else (schema.summary.api_key  or None)

    return AppSettings(
        stt=STTConfig(
            provider = STTProvider(schema.stt.provider),
            model    = schema.stt.model,
            language = schema.stt.language,
            api_url  = schema.stt.api_url or None,
            api_key  = stt_key,
        ),
        translation=TranslationConfig(
            provider        = TranslationProvider(schema.translation.provider),
            model           = schema.translation.model,
            api_url         = schema.translation.api_url or None,
            api_key         = trans_key,
            prompt_template = schema.translation.prompt_template or None,
        ),
        summary=SummaryConfig(
            provider        = SummaryProvider(schema.summary.provider),
            model           = schema.summary.model,
            api_url         = schema.summary.api_url or None,
            api_key         = summ_key,
            prompt_template = schema.summary.prompt_template or None,
        ),
        embedding=current.embedding,  # preserve embedding config on settings save
    )


# ── Routes ────────────────────────────────────────────────────────────────────

@router.get(
    "/config",
    summary="Get current user's provider configuration",
    tags=["config"],
    responses={401: {"description": "Not authenticated"}},
)
async def get_config(current_user: User = Depends(get_current_user)):
    svc = ConfigService(current_user.id)
    return _mask(svc.get())


@router.put(
    "/config",
    summary="Save provider configuration for the current user",
    tags=["config"],
    responses={401: {"description": "Not authenticated"}},
)
async def put_config(body: AppSettingsSchema, current_user: User = Depends(get_current_user)):
    svc = ConfigService(current_user.id)
    try:
        settings = _schema_to_domain(body, svc.get())
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    svc.save(settings)
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


@router.post(
    "/config/test/translation",
    summary="Test the translation provider configuration",
    tags=["config"],
    responses={401: {"description": "Not authenticated"}, 502: {"description": "Provider error"}},
)
async def test_translation(
    body: Optional[TranslationConfigSchema] = None,
    current_user: User = Depends(get_current_user),
):
    stored = ConfigService(current_user.id).get()
    cfg = _trans_schema_to_cfg(body, stored.translation) if body else stored.translation
    return await TranslationService(cfg).test()


@router.post(
    "/config/test/stt",
    summary="Test the STT provider configuration",
    tags=["config"],
    responses={401: {"description": "Not authenticated"}, 502: {"description": "Provider error"}},
)
async def test_stt(
    body: Optional[STTConfigSchema] = None,
    current_user: User = Depends(get_current_user),
):
    stored = ConfigService(current_user.id).get()
    cfg = _stt_schema_to_cfg(body, stored.stt) if body else stored.stt
    return await STTService(cfg).test()


@router.post(
    "/config/test/summary",
    summary="Test the summary provider configuration",
    tags=["config"],
    responses={401: {"description": "Not authenticated"}, 502: {"description": "Provider error"}},
)
async def test_summary(
    body: Optional[SummaryConfigSchema] = None,
    current_user: User = Depends(get_current_user),
):
    stored = ConfigService(current_user.id).get()
    cfg = _summary_schema_to_cfg(body, stored.summary) if body else stored.summary
    return await SummaryService(cfg).test()


@router.post(
    "/config/reset",
    summary="Reset configuration to global defaults (removes per-user overrides)",
    tags=["config"],
    responses={401: {"description": "Not authenticated"}},
)
async def reset_config(current_user: User = Depends(get_current_user)):
    svc = ConfigService(current_user.id)
    return _mask(svc.reset())
