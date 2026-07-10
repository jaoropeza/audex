from __future__ import annotations

import queue
import threading
from typing import Optional

from domain.ports.audio_capture_port import AudioCapturePort
from adapters.audio.dshow_mic_adapter import DShowMicAdapter
from adapters.audio.wasapi_loopback_adapter import WASAPILoopbackAdapter


class MergeAdapter(AudioCapturePort):
    """Runs both mic (DShow) and loopback (WASAPI) and merges into one queue."""

    def __init__(self, mic_device: str, loopback_hint: Optional[str] = None) -> None:
        self._mic      = DShowMicAdapter(mic_device)
        self._loopback = WASAPILoopbackAdapter(loopback_hint)

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
        mic_thread = threading.Thread(
            target=self._mic.stream,
            kwargs=dict(
                audio_queue=audio_queue,
                stop_event=stop_event,
                chunk_seconds=chunk_seconds,
                overlap_seconds=overlap_seconds,
                label="MIC",
                debug=debug,
                audio_saver=audio_saver,
            ),
            daemon=True,
        )
        spk_thread = threading.Thread(
            target=self._loopback.stream,
            kwargs=dict(
                audio_queue=audio_queue,
                stop_event=stop_event,
                chunk_seconds=chunk_seconds,
                overlap_seconds=overlap_seconds,
                label="SPK",
                debug=debug,
                audio_saver=audio_saver,
            ),
            daemon=True,
        )
        mic_thread.start()
        spk_thread.start()
        mic_thread.join()
        spk_thread.join()

    def close(self) -> None:
        self._mic.close()
        self._loopback.close()
