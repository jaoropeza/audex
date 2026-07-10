from __future__ import annotations

import queue
import threading
from abc import ABC, abstractmethod
from typing import Optional


class STTPort(ABC):
    """
    Synchronous chunk-level transcription interface.

    transcribe_chunk() is called from a background thread (not an async loop),
    so it must be blocking-safe.  health_check() is async for use in the
    FastAPI web server.
    """

    @abstractmethod
    def transcribe_chunk(
        self,
        label: str,
        raw_audio: bytes,
        language: str,
    ) -> Optional[str]:
        """
        Process one PCM-16 audio chunk.

        Returns a formatted "[HH:MM:SS][LABEL] text" line ready to append to
        the transcript file, or None if the chunk is silent / a hallucination /
        contains no speech.
        """

    @abstractmethod
    def transcribe_segments(
        self,
        raw_audio: bytes,
        language: str,
    ) -> list:
        """
        Return raw Whisper / API segments (with timestamps) for diarization
        alignment.  Each element must have .text, .start, .end, .words attrs.
        Returns [] for silence / no speech.
        """

    @abstractmethod
    async def health_check(self) -> dict:
        """Return {"ok": bool, "detail": str, ...}."""
