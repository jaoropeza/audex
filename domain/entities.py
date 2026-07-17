from __future__ import annotations

import dataclasses
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional


# ── Auth entities ─────────────────────────────────────────────────────────────

class UserRole(str, Enum):
    USER  = "user"
    ADMIN = "admin"


@dataclass
class User:
    id:            int
    username:      str
    email:         Optional[str]
    hashed_pw:     str
    role:          UserRole
    is_active:     bool
    settings_json: Optional[str]  # JSON string; None = use global default
    created_at:    str


# ── Transcript entity ─────────────────────────────────────────────────────────

@dataclass
class Transcript:
    id:         int
    user_id:    Optional[int]
    filename:   str
    content:    Optional[str]
    created_at: str
    indexed_at: str
    line_count: int


# ── Category entity ───────────────────────────────────────────────────────────

@dataclass
class Category:
    id:          int
    user_id:     int
    name:        str
    description: Optional[str]
    color:       str
    created_at:  str


# ── Embedding config ──────────────────────────────────────────────────────────

class EmbeddingProvider(str, Enum):
    NONE   = "none"
    OLLAMA = "ollama"
    OPENAI = "openai"


class EmbeddingChunkStrategy(str, Enum):
    LINES        = "lines"
    SPEAKER_TURN = "speaker_turn"
    TIME_WINDOW  = "time_window"


@dataclass
class EmbeddingConfig:
    enabled:          bool                   = False
    provider:         EmbeddingProvider      = EmbeddingProvider.NONE
    model:            str                    = "nomic-embed-text"
    api_url:          Optional[str]          = None
    api_key:          Optional[str]          = None
    chunk_strategy:   EmbeddingChunkStrategy = EmbeddingChunkStrategy.LINES
    chunk_size:       int                    = 30
    time_window_secs: int                    = 60


class STTProvider(str, Enum):
    FASTER_WHISPER = "faster_whisper"
    PARAKEET_NIM   = "parakeet_nim"
    PARAKEET_NEMO  = "parakeet_nemo"


class TranslationProvider(str, Enum):
    ANTHROPIC = "anthropic"
    OLLAMA    = "ollama"
    OPENAI    = "openai"
    GEMINI    = "gemini"


class SummaryProvider(str, Enum):
    ANTHROPIC = "anthropic"
    OLLAMA    = "ollama"
    OPENAI    = "openai"
    GEMINI    = "gemini"


@dataclass
class STTConfig:
    provider: STTProvider   = STTProvider.FASTER_WHISPER
    model:    str           = "large-v3"
    language: str           = "es"
    api_url:  Optional[str] = None
    api_key:  Optional[str] = None


@dataclass
class TranslationConfig:
    provider:        TranslationProvider = TranslationProvider.ANTHROPIC
    model:           str                 = "claude-haiku-4-5-20251001"
    api_url:         Optional[str]       = None
    api_key:         Optional[str]       = None
    prompt_template: Optional[str]       = None


@dataclass
class SummaryConfig:
    provider:        SummaryProvider = SummaryProvider.ANTHROPIC
    model:           str             = "claude-haiku-4-5-20251001"
    api_url:         Optional[str]   = None
    api_key:         Optional[str]   = None
    prompt_template: Optional[str]   = None


@dataclass
class AppSettings:
    stt:         STTConfig         = field(default_factory=STTConfig)
    translation: TranslationConfig = field(default_factory=TranslationConfig)
    summary:     SummaryConfig     = field(default_factory=SummaryConfig)
    embedding:   EmbeddingConfig   = field(default_factory=EmbeddingConfig)

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
                "provider":        self.translation.provider.value,
                "model":           self.translation.model,
                "api_url":         self.translation.api_url,
                "api_key":         self.translation.api_key,
                "prompt_template": self.translation.prompt_template,
            },
            "summary": {
                "provider":        self.summary.provider.value,
                "model":           self.summary.model,
                "api_url":         self.summary.api_url,
                "api_key":         self.summary.api_key,
                "prompt_template": self.summary.prompt_template,
            },
            "embedding": {
                "enabled":          self.embedding.enabled,
                "provider":         self.embedding.provider.value,
                "model":            self.embedding.model,
                "api_url":          self.embedding.api_url,
                "api_key":          self.embedding.api_key,
                "chunk_strategy":   self.embedding.chunk_strategy.value,
                "chunk_size":       self.embedding.chunk_size,
                "time_window_secs": self.embedding.time_window_secs,
            },
        }

    @classmethod
    def from_dict(cls, d: dict) -> "AppSettings":
        stt_d   = d.get("stt", {})
        trans_d = d.get("translation", {})
        summ_d  = d.get("summary", {})
        emb_d   = d.get("embedding", {})
        return cls(
            stt=STTConfig(
                provider = STTProvider(stt_d.get("provider", STTProvider.FASTER_WHISPER)),
                model    = stt_d.get("model", "large-v3"),
                language = stt_d.get("language", "es"),
                api_url  = stt_d.get("api_url"),
                api_key  = stt_d.get("api_key"),
            ),
            translation=TranslationConfig(
                provider        = TranslationProvider(trans_d.get("provider", TranslationProvider.ANTHROPIC)),
                model           = trans_d.get("model", "claude-haiku-4-5-20251001"),
                api_url         = trans_d.get("api_url"),
                api_key         = trans_d.get("api_key"),
                prompt_template = trans_d.get("prompt_template"),
            ),
            summary=SummaryConfig(
                provider        = SummaryProvider(summ_d.get("provider", SummaryProvider.ANTHROPIC)),
                model           = summ_d.get("model", "claude-haiku-4-5-20251001"),
                api_url         = summ_d.get("api_url"),
                api_key         = summ_d.get("api_key"),
                prompt_template = summ_d.get("prompt_template"),
            ),
            embedding=EmbeddingConfig(
                enabled          = bool(emb_d.get("enabled", False)),
                provider         = EmbeddingProvider(emb_d.get("provider", EmbeddingProvider.NONE)),
                model            = emb_d.get("model", "nomic-embed-text"),
                api_url          = emb_d.get("api_url"),
                api_key          = emb_d.get("api_key"),
                chunk_strategy   = EmbeddingChunkStrategy(emb_d.get("chunk_strategy", EmbeddingChunkStrategy.LINES)),
                chunk_size       = int(emb_d.get("chunk_size", 30)),
                time_window_secs = int(emb_d.get("time_window_secs", 60)),
            ),
        )
