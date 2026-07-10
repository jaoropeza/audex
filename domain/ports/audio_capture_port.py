from __future__ import annotations

import queue
import threading
from abc import ABC, abstractmethod


class AudioCapturePort(ABC):
    """
    Streams raw PCM-16 audio chunks into a shared queue.

    Implementations run in their own thread and push (label, bytes) tuples
    into audio_queue until stop_event is set.
    """

    @abstractmethod
    def stream(
        self,
        audio_queue: "queue.Queue[tuple[str, bytes]]",
        stop_event: threading.Event,
        chunk_seconds: float,
        overlap_seconds: float,
        label: str = "",
        debug: bool = False,
        audio_saver=None,
    ) -> None:
        """Blocking call — run inside a daemon thread."""

    @abstractmethod
    def close(self) -> None:
        """Release any held resources (file handles, OS streams)."""
