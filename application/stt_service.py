from __future__ import annotations

from domain.entities import STTConfig, STTProvider
from domain.ports.stt_port import STTPort


class STTService:
    def __init__(self, config: STTConfig) -> None:
        self._config = config
        self._adapter: STTPort | None = None

    def get_adapter(self) -> STTPort:
        if self._adapter is None:
            self._adapter = self._build_adapter()
        return self._adapter

    def _build_adapter(self) -> STTPort:
        match self._config.provider:
            case STTProvider.FASTER_WHISPER:
                from adapters.stt.faster_whisper_adapter import FasterWhisperAdapter
                return FasterWhisperAdapter(self._config)
            case STTProvider.PARAKEET_NIM:
                from adapters.stt.parakeet_nim_adapter import ParakeetNIMAdapter
                return ParakeetNIMAdapter(self._config)
            case STTProvider.PARAKEET_NEMO:
                from adapters.stt.parakeet_nemo_adapter import ParakeetNeMoAdapter
                return ParakeetNeMoAdapter(self._config)
            case _:
                raise ValueError(f"Unknown STT provider: {self._config.provider}")

    async def test(self) -> dict:
        try:
            return await self.get_adapter().health_check()
        except Exception as exc:
            return {"ok": False, "detail": str(exc)}
