from __future__ import annotations

import io
import tempfile
import wave
from datetime import datetime
from typing import Optional

import numpy as np

from domain.entities import STTConfig
from domain.ports.stt_port import STTPort

SAMPLE_RATE      = 16000
CHANNELS         = 1
BYTES_PER_SAMPLE = 2
_DEFAULT_MODEL   = "nvidia/parakeet-tdt-0.6b-v3"


def _pcm_to_wav_bytes(raw: bytes) -> bytes:
    buf = io.BytesIO()
    with wave.open(buf, "wb") as wf:
        wf.setnchannels(CHANNELS)
        wf.setsampwidth(BYTES_PER_SAMPLE)
        wf.setframerate(SAMPLE_RATE)
        wf.writeframes(raw)
    return buf.getvalue()


class ParakeetNIMAdapter(STTPort):
    """
    Calls NVIDIA NIM (or any OpenAI-compatible /v1/audio/transcriptions endpoint)
    to transcribe audio chunks using the Parakeet model.
    """

    def __init__(self, config: STTConfig) -> None:
        self._config = config
        if not config.api_url:
            raise ValueError(
                "Parakeet NIM requires api_url (e.g. https://integrate.api.nvidia.com/v1)"
            )

    def _post(self, wav_bytes: bytes) -> str:
        import httpx
        url     = self._config.api_url.rstrip("/") + "/audio/transcriptions"
        headers = {"Authorization": f"Bearer {self._config.api_key or ''}"}
        model   = self._config.model or _DEFAULT_MODEL
        with httpx.Client(timeout=30.0) as client:
            resp = client.post(
                url,
                headers=headers,
                files={"file": ("audio.wav", wav_bytes, "audio/wav")},
                data={"model": model, "response_format": "json"},
            )
            resp.raise_for_status()
            return resp.json().get("text", "")

    def transcribe_chunk(self, label: str, raw_audio: bytes, language: str) -> Optional[str]:
        arr = np.frombuffer(raw_audio, dtype=np.int16).astype(np.float32) / 32768.0
        if arr.size == 0 or float(np.sqrt(np.mean(arr ** 2))) < 0.003:
            return None
        try:
            text = self._post(_pcm_to_wav_bytes(raw_audio)).strip()
        except Exception as exc:
            print(f"[ERROR] Parakeet NIM transcription failed: {exc}")
            return None
        if not text:
            return None
        ts = datetime.now().strftime("%H:%M:%S")
        parts = [f"[{ts}]"]
        if label:
            parts.append(f"[{label}]")
        parts.append(" " + text)
        return "".join(parts)

    def transcribe_segments(self, raw_audio: bytes, language: str) -> list:
        # NIM returns only a text string — no word-level timestamps available
        return []

    async def health_check(self) -> dict:
        import httpx
        try:
            url = self._config.api_url.rstrip("/") + "/models"
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.get(url, headers={"Authorization": f"Bearer {self._config.api_key or ''}"})
                resp.raise_for_status()
            return {"ok": True, "detail": f"NVIDIA NIM reachable at {self._config.api_url}"}
        except Exception as exc:
            return {"ok": False, "detail": str(exc)}
