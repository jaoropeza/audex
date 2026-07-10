from __future__ import annotations

from abc import ABC, abstractmethod


class TranslationPort(ABC):
    @abstractmethod
    async def translate(
        self,
        texts: list[str],
        target_language: str,
        source_language: str = "auto",
        prompt_template: str | None = None,
    ) -> list[str]:
        """Translate a batch of plain-text strings. Returns same-length list."""

    @abstractmethod
    async def health_check(self) -> dict:
        """Return {"ok": bool, "detail": str}."""
