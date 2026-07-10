from __future__ import annotations

import queue
import threading
import time

import numpy as np

from domain.ports.audio_capture_port import AudioCapturePort

SAMPLE_RATE    = 16000
BYTES_PER_SAMPLE = 2
SILENCE_DB_THRESHOLD = -70.0
SILENCE_WARN_CHUNKS  = 10


def _rms_db(raw: bytes) -> float:
    arr = np.frombuffer(raw, dtype=np.int16).astype(np.float32)
    rms = float(np.sqrt(np.mean(arr ** 2))) if arr.size else 0.0
    return 20 * np.log10(rms / 32768.0 + 1e-9)


class WASAPILoopbackAdapter(AudioCapturePort):
    """Captures system speaker output via PyAudioWPatch WASAPI loopback."""

    def __init__(self, device_hint: str | None = None) -> None:
        self._device_hint = device_hint

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
        try:
            import pyaudiowpatch as pyaudio
        except ImportError:
            print("[ERROR] pyaudiowpatch not installed. Run: pip install pyaudiowpatch")
            stop_event.set()
            return

        p = pyaudio.PyAudio()
        target = self._find_device(p)
        if target is None:
            print("[ERROR] No loopback device found. Run --list-devices.")
            stop_event.set()
            p.terminate()
            return

        native_rate     = int(target["defaultSampleRate"])
        native_channels = min(int(target["maxInputChannels"]), 2)
        print(f"[INFO] Loopback capture from: {target['name']} @ {native_rate} Hz / {native_channels} ch")

        target_chunk_bytes = int(SAMPLE_RATE * chunk_seconds) * BYTES_PER_SAMPLE
        overlap_bytes      = int(SAMPLE_RATE * overlap_seconds) * BYTES_PER_SAMPLE
        frames_per_buffer  = native_rate // 10

        buf              = b""
        previous_overlap = b""
        chunk_count      = 0
        silent_streak    = 0

        def callback(in_data, _fc, _ti, _st):
            nonlocal buf, previous_overlap, chunk_count, silent_streak

            arr = np.frombuffer(in_data, dtype=np.int16).astype(np.float32)
            if native_channels == 2:
                arr = arr.reshape(-1, 2).mean(axis=1)
            if native_rate != SAMPLE_RATE:
                target_len = int(len(arr) * SAMPLE_RATE / native_rate)
                indices    = np.linspace(0, len(arr) - 1, target_len)
                arr        = np.interp(indices, np.arange(len(arr)), arr)

            buf += arr.clip(-32768, 32767).astype(np.int16).tobytes()

            while len(buf) >= target_chunk_bytes:
                chunk = buf[:target_chunk_bytes]
                buf   = buf[target_chunk_bytes:]
                chunk_count += 1
                db = _rms_db(chunk)

                if db < SILENCE_DB_THRESHOLD:
                    silent_streak += 1
                    if silent_streak == SILENCE_WARN_CHUNKS:
                        print(f"[WARN] Audio silent for {SILENCE_WARN_CHUNKS} chunks. Is audio playing?")
                else:
                    silent_streak = 0

                if debug:
                    bar = "#" * int(max(0, (db + 60) / 2))
                    tag = f"{label} " if label else ""
                    print(f"[AUDIO {tag}chunk={chunk_count:4d}  {db:6.1f} dB  |{bar:<30}|]")

                audio_queue.put((label, previous_overlap + chunk))
                if audio_saver:
                    audio_saver.write(chunk)
                previous_overlap = chunk[-overlap_bytes:] if len(chunk) >= overlap_bytes else chunk

            return (None, pyaudio.paContinue)

        stream = p.open(
            format=pyaudio.paInt16,
            channels=native_channels,
            rate=native_rate,
            frames_per_buffer=frames_per_buffer,
            input=True,
            input_device_index=target["index"],
            stream_callback=callback,
        )
        stream.start_stream()
        while not stop_event.is_set() and stream.is_active():
            time.sleep(0.1)
        stream.stop_stream()
        stream.close()
        p.terminate()

        # Flush any partial buffer (< chunk_seconds) to audio_saver
        if audio_saver and buf:
            audio_saver.write(buf)

        stop_event.set()

    def _find_device(self, p):
        for dev in p.get_loopback_device_info_generator():
            if self._device_hint is None or self._device_hint.lower() in dev["name"].lower():
                return dev
        # Fall back to default output device's loopback
        try:
            import pyaudiowpatch as pyaudio
            wasapi_info = p.get_host_api_info_by_type(pyaudio.paWASAPI)
            default_out = p.get_device_info_by_index(wasapi_info["defaultOutputDevice"])
            for dev in p.get_loopback_device_info_generator():
                if default_out["name"] in dev["name"]:
                    return dev
        except Exception:
            pass
        return None

    def close(self) -> None:
        pass  # PyAudio stream lifetime is managed inside stream()
