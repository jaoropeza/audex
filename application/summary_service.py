from __future__ import annotations

from domain.entities import SummaryConfig, TranslationConfig, TranslationProvider


class SummaryService:
    def __init__(self, config: SummaryConfig) -> None:
        self._config = config

    def _as_translation_config(self) -> TranslationConfig:
        return TranslationConfig(
            provider = TranslationProvider(self._config.provider.value),
            model    = self._config.model,
            api_url  = self._config.api_url,
            api_key  = self._config.api_key,
        )

    async def test(self) -> dict:
        try:
            from application.translation_service import TranslationService
            return await TranslationService(self._as_translation_config()).test()
        except Exception as exc:
            return {"ok": False, "detail": str(exc)}
