from __future__ import annotations

import io
import tempfile
import wave
from datetime import datetime
from pathlib import Path
from typing import Optional

import numpy as np

from domain.entities import STTConfig
from domain.ports.stt_port import STTPort

SAMPLE_RATE      = 16000
CHANNELS         = 1
BYTES_PER_SAMPLE = 2
_DOCKER_HINT = (
    "\n  To run Parakeet locally, use the provided Docker image:\n"
    "    docker compose -f docker/docker-compose.parakeet.yml up\n"
    "  Or install NeMo manually:\n"
    "    pip install nemo_toolkit[asr]\n"
)


def _pcm_to_wav_file(raw: bytes) -> str:
    tmp = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
    with wave.open(tmp.name, "wb") as wf:
        wf.setnchannels(CHANNELS)
        wf.setsampwidth(BYTES_PER_SAMPLE)
        wf.setframerate(SAMPLE_RATE)
        wf.writeframes(raw)
    return tmp.name


class ParakeetNeMoAdapter(STTPort):
    """
    Runs the NVIDIA Parakeet model locally using NVIDIA NeMo.

    Requires nemo_toolkit[asr] — heavy install (~5 GB).
    If not installed, the adapter raises a helpful RuntimeError pointing to
    docker/docker-compose.parakeet.yml.
    """

    def __init__(self, config: STTConfig) -> None:
        self._config = config
        self._model  = None

    def _ensure_model(self):
        if self._model is not None:
            return
        try:
            from nemo.collections.asr.models import ASRModel  # type: ignore[import]
        except ImportError:
            raise RuntimeError(
                "[ERROR] nemo_toolkit is not installed — cannot run Parakeet locally." + _DOCKER_HINT
            )
        model_name = self._config.model or "nvidia/parakeet-tdt-0.6b-v3"
        print(f"[INFO] Loading NeMo model: {model_name} (first load may download ~1 GB)…")
        self._model = ASRModel.from_pretrained(model_name)
        self._model.eval()
        print("[INFO] NeMo Parakeet model loaded.")

    def transcribe_chunk(self, label: str, raw_audio: bytes, language: str) -> Optional[str]:
        arr = np.frombuffer(raw_audio, dtype=np.int16).astype(np.float32) / 32768.0
        if arr.size == 0 or float(np.sqrt(np.mean(arr ** 2))) < 0.003:
            return None
        try:
            self._ensure_model()
        except RuntimeError as exc:
            print(str(exc))
            return None

        wav_path = _pcm_to_wav_file(raw_audio)
        try:
            results = self._model.transcribe([wav_path])
            text = results[0].strip() if results else ""
        except Exception as exc:
            print(f"[ERROR] NeMo transcription failed: {exc}")
            return None
        finally:
            Path(wav_path).unlink(missing_ok=True)

        if not text:
            return None
        ts = datetime.now().strftime("%H:%M:%S")
        parts = [f"[{ts}]"]
        if label:
            parts.append(f"[{label}]")
        parts.append(" " + text)
        return "".join(parts)

    def transcribe_segments(self, raw_audio: bytes, language: str) -> list:
        return []  # NeMo doesn't expose word-level timestamps in this interface

    async def health_check(self) -> dict:
        try:
            from nemo.collections.asr.models import ASRModel  # type: ignore[import]
            loaded = self._model is not None
            return {
                "ok":     True,
                "detail": f"NeMo available — model {'loaded' if loaded else 'not yet loaded (loads on first transcription)'}",
                "model":  self._config.model or "nvidia/parakeet-tdt-0.6b-v3",
            }
        except ImportError:
            return {
                "ok":     False,
                "detail": "nemo_toolkit not installed." + _DOCKER_HINT,
            }
