from __future__ import annotations

import queue
import subprocess
import sys
import threading

import numpy as np

from domain.ports.audio_capture_port import AudioCapturePort

FFMPEG_PATH      = "ffmpeg"
SAMPLE_RATE      = 16000
CHANNELS         = 1
BYTES_PER_SAMPLE = 2
SILENCE_DB_THRESHOLD = -70.0
SILENCE_WARN_CHUNKS  = 10
READ_SIZE            = 4096


def _rms_db(raw: bytes) -> float:
    arr = np.frombuffer(raw, dtype=np.int16).astype(np.float32)
    rms = float(np.sqrt(np.mean(arr ** 2))) if arr.size else 0.0
    return 20 * np.log10(rms / 32768.0 + 1e-9)


class DShowMicAdapter(AudioCapturePort):
    """Captures microphone audio via FFmpeg DirectShow on Windows."""

    def __init__(self, device_name: str, debug: bool = False) -> None:
        self._device_name = device_name
        self._debug       = debug
        self._process: subprocess.Popen | None = None

    def _start_ffmpeg(self) -> subprocess.Popen:
        command = [
            FFMPEG_PATH, "-hide_banner",
            "-loglevel", "warning" if self._debug else "error",
            "-f", "dshow",
            "-i", f"audio={self._device_name}",
            "-ac", str(CHANNELS),
            "-ar", str(SAMPLE_RATE),
            "-fflags", "nobuffer",
            "-flags", "low_delay",
            "-f", "s16le", "-",
        ]
        print(f"[INFO] Starting microphone capture from: {self._device_name}")
        try:
            return subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, bufsize=0)
        except FileNotFoundError:
            print("[ERROR] ffmpeg not found.")
            sys.exit(1)

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
        process = self._start_ffmpeg()
        self._process = process

        # Drain stderr in a background thread to avoid pipe deadlock
        def _drain_stderr():
            for raw in process.stderr:
                msg = raw.decode(errors="ignore").strip()
                if msg:
                    print(f"[FFMPEG] {msg}")

        threading.Thread(target=_drain_stderr, daemon=True).start()

        chunk_bytes   = int(SAMPLE_RATE * chunk_seconds) * BYTES_PER_SAMPLE
        overlap_bytes = int(SAMPLE_RATE * overlap_seconds) * BYTES_PER_SAMPLE
        buf              = b""
        previous_overlap = b""
        chunk_count      = 0
        silent_streak    = 0

        while not stop_event.is_set():
            data = process.stdout.read(READ_SIZE)
            if not data:
                print("[WARN] FFmpeg stopped sending audio.")
                break
            buf += data

            while len(buf) >= chunk_bytes:
                raw_chunk = buf[:chunk_bytes]
                buf       = buf[chunk_bytes:]
                chunk_count += 1
                db = _rms_db(raw_chunk)

                if db < SILENCE_DB_THRESHOLD:
                    silent_streak += 1
                    if silent_streak == SILENCE_WARN_CHUNKS:
                        print(f"[WARN] Audio silent for {SILENCE_WARN_CHUNKS} chunks. Is the microphone active?")
                else:
                    silent_streak = 0

                if debug:
                    bar = "#" * int(max(0, (db + 60) / 2))
                    tag = f"{label} " if label else ""
                    print(f"[AUDIO {tag}chunk={chunk_count:4d}  {db:6.1f} dB  |{bar:<30}|]")

                audio_queue.put((label, previous_overlap + raw_chunk))
                if audio_saver:
                    audio_saver.write(raw_chunk)
                previous_overlap = raw_chunk[-overlap_bytes:] if len(raw_chunk) >= overlap_bytes else raw_chunk

        # Flush any partial buffer (< chunk_seconds) to audio_saver
        if audio_saver and buf:
            audio_saver.write(buf)

        stop_event.set()

    def close(self) -> None:
        if self._process:
            try:
                self._process.terminate()
                self._process.wait(timeout=5)
            except Exception:
                self._process.kill()
            self._process = None
