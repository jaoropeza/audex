from __future__ import annotations

import collections
import re
from datetime import datetime
from typing import Optional

import numpy as np

from domain.entities import STTConfig
from domain.ports.stt_port import STTPort

# ── Constants ─────────────────────────────────────────────────────────────────
SAMPLE_RATE              = 16000
TRANSCRIBE_RMS_MIN       = 0.003
WHISPER_NO_SPEECH_THRESHOLD = 0.6
WHISPER_LOG_PROB_THRESHOLD  = -1.0
WHISPER_COMPRESSION_RATIO   = 2.4
REPEAT_SUPPRESS_N           = 2

_GHOST_PHRASES = {
    "gracias", "gracias por ver el video", "gracias por ver",
    "gracias por su atención", "chau", "adios", "adiós",
    "hasta luego", "hasta pronto", "suscríbete", "suscribete",
    "subtítulos en español", "subtítulos realizados por",
    "thanks for watching", "thank you for watching", "thank you",
    "thanks", "bye", "goodbye", "see you next time",
    "please subscribe", "like and subscribe", "subtitles by",
}


# ── Helpers ───────────────────────────────────────────────────────────────────

def _clean_text(text: str) -> str:
    return re.sub(r"[^\w\s]", "", text, flags=re.UNICODE).strip().lower()


def _is_hallucination(text: str, recent: collections.deque) -> bool:
    if not text:
        return True
    clean = _clean_text(text)
    if not clean:
        return True
    if clean in _GHOST_PHRASES:
        return True
    if sum(1 for r in recent if r == clean) >= REPEAT_SUPPRESS_N:
        return True
    return False


def _strip_prefix_overlap(new_text: str, last_words: list) -> str:
    if not new_text or not last_words:
        return new_text
    new_words  = new_text.split()
    norm_new   = [_clean_text(w) for w in new_words]
    norm_last  = [_clean_text(w) for w in last_words]
    check = min(12, len(norm_last), len(norm_new))
    for n in range(check, 0, -1):
        if norm_last[-n:] == norm_new[:n]:
            return " ".join(new_words[n:]).strip()
    return new_text


def _format_line(ts: str, label: str, speaker: str, text: str) -> str:
    parts = [f"[{ts}]"]
    if label:
        parts.append(f"[{label}]")
    if speaker:
        parts.append(f"[{speaker}]")
    parts.append(" " + text)
    return "".join(parts)


def _pcm_to_float32(raw: bytes) -> Optional[np.ndarray]:
    arr = np.frombuffer(raw, dtype=np.int16)
    if arr.size == 0:
        return None
    return arr.astype(np.float32) / 32768.0


# ── Adapter ───────────────────────────────────────────────────────────────────

class FasterWhisperAdapter(STTPort):
    """
    Wraps faster-whisper WhisperModel.

    Maintains per-instance state (recent_texts, last_output_words) so that
    hallucination suppression and overlap deduplication work correctly across
    sequential transcribe_chunk() calls within one recording session.
    """

    def __init__(self, config: STTConfig) -> None:
        self._config      = config
        self._model       = None
        self._device      = None
        self._compute_type = None
        self._recent: collections.deque = collections.deque(maxlen=REPEAT_SUPPRESS_N + 1)
        self._last_words: list[str]     = []

    def _ensure_model(self):
        if self._model is not None:
            return
        from faster_whisper import WhisperModel
        device, compute_type = self._detect_device()
        self._device       = device
        self._compute_type = compute_type
        print(f"[INFO] Loading Whisper model '{self._config.model}' on {device}/{compute_type}...")
        self._model = WhisperModel(self._config.model, device=device, compute_type=compute_type)
        print("[INFO] Model loaded. Listening…")

    @staticmethod
    def _detect_device() -> tuple[str, str]:
        try:
            import ctranslate2
            if ctranslate2.get_cuda_device_count() > 0:
                return "cuda", "float16"
        except Exception:
            pass
        return "cpu", "int8"

    def transcribe_chunk(self, label: str, raw_audio: bytes, language: str) -> Optional[str]:
        self._ensure_model()
        audio = _pcm_to_float32(raw_audio)
        if audio is None:
            return None
        if float(np.sqrt(np.mean(audio ** 2))) < TRANSCRIBE_RMS_MIN:
            return None

        try:
            segments, _ = self._model.transcribe(
                audio,
                language=language if language != "auto" else None,
                beam_size=1,
                vad_filter=True,
                condition_on_previous_text=False,
                without_timestamps=True,
                no_speech_threshold=WHISPER_NO_SPEECH_THRESHOLD,
                log_prob_threshold=WHISPER_LOG_PROB_THRESHOLD,
                compression_ratio_threshold=WHISPER_COMPRESSION_RATIO,
            )
            text = " ".join(s.text.strip() for s in segments if s.text.strip())
        except Exception as exc:
            print(f"[ERROR] Transcription failed: {exc}")
            return None

        text  = _strip_prefix_overlap(text, self._last_words)
        clean = _clean_text(text)
        if _is_hallucination(text, self._recent):
            self._recent.append(clean)
            return None
        self._recent.append(clean)
        self._last_words = (self._last_words + text.split())[-20:]
        ts = datetime.now().strftime("%H:%M:%S")
        return _format_line(ts, label, "", text)

    def transcribe_segments(self, raw_audio: bytes, language: str) -> list:
        """Return raw Whisper segments with word timestamps (for diarization)."""
        self._ensure_model()
        audio = _pcm_to_float32(raw_audio)
        if audio is None:
            return []
        if float(np.sqrt(np.mean(audio ** 2))) < TRANSCRIBE_RMS_MIN:
            return []
        try:
            segments, _ = self._model.transcribe(
                audio,
                language=language if language != "auto" else None,
                beam_size=1,
                vad_filter=True,
                condition_on_previous_text=False,
                word_timestamps=True,
                no_speech_threshold=WHISPER_NO_SPEECH_THRESHOLD,
                log_prob_threshold=WHISPER_LOG_PROB_THRESHOLD,
                compression_ratio_threshold=WHISPER_COMPRESSION_RATIO,
            )
            return list(segments)
        except Exception as exc:
            print(f"[ERROR] Transcription (segments) failed: {exc}")
            return []

    def reset_session(self) -> None:
        """Call between recording sessions to clear dedup state."""
        self._recent.clear()
        self._last_words = []

    async def health_check(self) -> dict:
        device, compute_type = self._detect_device()
        return {
            "ok":           True,
            "detail":       f"FasterWhisper ready — model '{self._config.model}' on {device}/{compute_type}",
            "model":        self._config.model,
            "device":       device,
            "compute_type": compute_type,
            "loaded":       self._model is not None,
        }
