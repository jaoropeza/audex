from __future__ import annotations

from domain.entities import TranslationConfig, TranslationProvider
from domain.ports.translation_port import TranslationPort


class TranslationService:
    def __init__(self, config: TranslationConfig) -> None:
        self._config = config
        self._adapter: TranslationPort | None = None

    def get_adapter(self) -> TranslationPort:
        if self._adapter is None:
            self._adapter = self._build_adapter()
        return self._adapter

    def _build_adapter(self) -> TranslationPort:
        match self._config.provider:
            case TranslationProvider.ANTHROPIC:
                from adapters.translation.anthropic_adapter import AnthropicAdapter
                return AnthropicAdapter(self._config)
            case TranslationProvider.OLLAMA:
                from adapters.translation.ollama_adapter import OllamaAdapter
                return OllamaAdapter(self._config)
            case TranslationProvider.OPENAI:
                from adapters.translation.openai_adapter import OpenAIAdapter
                return OpenAIAdapter(self._config)
            case TranslationProvider.GEMINI:
                from adapters.translation.gemini_adapter import GeminiAdapter
                return GeminiAdapter(self._config)
            case _:
                raise ValueError(f"Unknown translation provider: {self._config.provider}")

    async def translate(
        self,
        texts: list[str],
        target_language: str,
        source_language: str = "auto",
        prompt_template: str | None = None,
    ) -> list[str]:
        return await self.get_adapter().translate(
            texts, target_language,
            source_language=source_language,
            prompt_template=prompt_template,
        )

    async def test(self) -> dict:
        try:
            return await self.get_adapter().health_check()
        except Exception as exc:
            return {"ok": False, "detail": str(exc)}
