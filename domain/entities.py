from __future__ import annotations

import dataclasses
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional


class STTProvider(str, Enum):
    FASTER_WHISPER = "faster_whisper"
    PARAKEET_NIM   = "parakeet_nim"
    PARAKEET_NEMO  = "parakeet_nemo"


class TranslationProvider(str, Enum):
    ANTHROPIC = "anthropic"
    OLLAMA    = "ollama"
    OPENAI    = "openai"
    GEMINI    = "gemini"


@dataclass
class STTConfig:
    provider: STTProvider   = STTProvider.FASTER_WHISPER
    model:    str           = "small"
    language: str           = "en"
    api_url:  Optional[str] = None
    api_key:  Optional[str] = None


@dataclass
class TranslationConfig:
    provider: TranslationProvider = TranslationProvider.ANTHROPIC
    model:    str                 = "claude-haiku-4-5-20251001"
    api_url:  Optional[str]       = None
    api_key:  Optional[str]       = None


@dataclass
class AppSettings:
    stt:         STTConfig         = field(default_factory=STTConfig)
    translation: TranslationConfig = field(default_factory=TranslationConfig)

    def to_dict(self) -> dict:
        return {
            "stt": {
                "provider": self.stt.provider.value,
                "model":    self.stt.model,
                "language": self.stt.language,
                "api_url":  self.stt.api_url,
                "api_key":  self.stt.api_key,
            },
            "translation": {
                "provider": self.translation.provider.value,
                "model":    self.translation.model,
                "api_url":  self.translation.api_url,
                "api_key":  self.translation.api_key,
            },
        }

    @classmethod
    def from_dict(cls, d: dict) -> "AppSettings":
        stt_d   = d.get("stt", {})
        trans_d = d.get("translation", {})
        return cls(
            stt=STTConfig(
                provider = STTProvider(stt_d.get("provider", STTProvider.FASTER_WHISPER)),
                model    = stt_d.get("model", "small"),
                language = stt_d.get("language", "en"),
                api_url  = stt_d.get("api_url"),
                api_key  = stt_d.get("api_key"),
            ),
            translation=TranslationConfig(
                provider = TranslationProvider(trans_d.get("provider", TranslationProvider.ANTHROPIC)),
                model    = trans_d.get("model", "claude-haiku-4-5-20251001"),
                api_url  = trans_d.get("api_url"),
                api_key  = trans_d.get("api_key"),
            ),
        )
