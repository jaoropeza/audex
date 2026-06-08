import os
import subprocess
import queue
import threading
import time
import sys
import re
import argparse
from datetime import datetime

os.environ.setdefault("HF_HUB_DISABLE_SYMLINKS_WARNING", "1")

import numpy as np
from faster_whisper import WhisperModel


# =========================
# Defaults
# =========================

FFMPEG_PATH = "ffmpeg"
SAMPLE_RATE = 16000
CHANNELS = 1
BYTES_PER_SAMPLE = 2  # int16 = 2 bytes

DEFAULT_MODEL = "small"
DEFAULT_LANGUAGE = "en"
DEFAULT_CHUNK_SECONDS = 5
DEFAULT_OVERLAP_SECONDS = 1
OUTPUT_FILE = "transcript.txt"


# =========================
# Audio device discovery
# =========================

def list_audio_devices():
    """Lists available DirectShow audio input devices via ffmpeg."""
    print("Querying available audio devices...\n")

    # Check ffmpeg is reachable first
    try:
        subprocess.run([FFMPEG_PATH, "-version"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except FileNotFoundError:
        print("[ERROR] ffmpeg not found. Install it and add it to your PATH.")
        print("  Download: https://www.gyan.dev/ffmpeg/builds/")
        return []

    # NOTE: do NOT use -hide_banner here — it can suppress dshow device output
    command = [
        FFMPEG_PATH,
        "-list_devices", "true",
        "-f", "dshow",
        "-i", "dummy"
    ]
    result = subprocess.run(
        command,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.PIPE
    )
    output = result.stderr.decode(errors="ignore")

    devices = []

    # ffmpeg >= 7.x: `"Device Name" (audio)` on each line (no separate sections)
    for line in output.splitlines():
        m = re.search(r'"(.+?)"\s+\(audio\)', line)
        if m:
            name = m.group(1)
            devices.append(name)
            print(f'  "{name}"')

    # ffmpeg < 7.x fallback: separate "DirectShow audio devices" section
    if not devices:
        in_audio = False
        for line in output.splitlines():
            if "DirectShow audio devices" in line:
                in_audio = True
                continue
            if not in_audio or "Alternative name" in line:
                continue
            m = re.search(r'"([^@][^"]*)"', line)
            if m:
                name = m.group(1)
                devices.append(name)
                print(f'  "{name}"')

    if not devices:
        print("  No audio devices found.\n")
        print("  Raw ffmpeg output (for diagnosis):")
        for line in output.splitlines():
            print(f"    {line}")

    return devices


# =========================
# CUDA detection
# =========================

def detect_device():
    """Returns ('cuda', 'float16') if a CUDA GPU is available, else ('cpu', 'int8').

    Uses CTranslate2 (the actual faster-whisper backend) for detection,
    with a torch fallback for the GPU name display.
    """
    try:
        import ctranslate2
        if ctranslate2.get_cuda_device_count() > 0:
            gpu_name = "unknown GPU"
            try:
                import torch
                if torch.cuda.is_available():
                    gpu_name = torch.cuda.get_device_name(0)
            except ImportError:
                pass
            print(f"[INFO] GPU detected: {gpu_name} — using CUDA/float16")
            return "cuda", "float16"
    except (ImportError, Exception):
        pass
    print("[INFO] No CUDA GPU detected — using CPU/int8")
    return "cpu", "int8"


# =========================
# FFmpeg capture
# =========================

def start_ffmpeg(audio_device):
    command = [
        FFMPEG_PATH,
        "-hide_banner",
        "-loglevel", "error",
        "-f", "dshow",
        "-i", f"audio={audio_device}",
        "-ac", str(CHANNELS),
        "-ar", str(SAMPLE_RATE),
        "-fflags", "nobuffer",
        "-flags", "low_delay",
        "-f", "s16le",
        "-"
    ]
    print(f"[INFO] Starting FFmpeg with device: {audio_device}")
    try:
        process = subprocess.Popen(
            command,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            bufsize=0
        )
    except FileNotFoundError:
        print("[ERROR] ffmpeg not found. Add ffmpeg.exe to your PATH.")
        sys.exit(1)
    return process


def ffmpeg_error_reader(process, stop_event):
    while not stop_event.is_set():
        line = process.stderr.readline()
        if not line:
            break
        message = line.decode(errors="ignore").strip()
        if message:
            print(f"[FFMPEG] {message}")


def audio_reader(process, audio_queue, stop_event, chunk_bytes, overlap_bytes):
    previous_overlap = b""
    while not stop_event.is_set():
        raw_chunk = process.stdout.read(chunk_bytes)
        if not raw_chunk:
            print("[WARN] FFmpeg stopped sending audio.")
            break
        audio_queue.put(previous_overlap + raw_chunk)
        previous_overlap = raw_chunk[-overlap_bytes:] if len(raw_chunk) >= overlap_bytes else raw_chunk
    stop_event.set()


# =========================
# Transcription
# =========================

def pcm_to_float32(raw_audio):
    arr = np.frombuffer(raw_audio, dtype=np.int16)
    if arr.size == 0:
        return None
    return arr.astype(np.float32) / 32768.0


def append_transcript(text, output_file):
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with open(output_file, "a", encoding="utf-8") as f:
        f.write(f"[{ts}] {text}\n")


def transcriber(audio_queue, stop_event, model_size, device, compute_type, language, output_file):
    print(f"[INFO] Loading Whisper model '{model_size}' on {device}/{compute_type}...")
    model = WhisperModel(model_size, device=device, compute_type=compute_type)
    print("[INFO] Model loaded. Listening... (Ctrl+C to stop)\n")

    while not stop_event.is_set():
        try:
            raw_audio = audio_queue.get(timeout=1)
        except queue.Empty:
            continue

        audio = pcm_to_float32(raw_audio)
        if audio is None:
            continue

        try:
            segments, _ = model.transcribe(
                audio,
                language=language if language != "auto" else None,
                beam_size=1,
                vad_filter=True,
                condition_on_previous_text=False,
                without_timestamps=True
            )
            text = " ".join(s.text.strip() for s in segments if s.text.strip())
            if text:
                ts = datetime.now().strftime("%H:%M:%S")
                print(f"[{ts}] {text}")
                append_transcript(text, output_file)
        except Exception as e:
            print(f"[ERROR] Transcription failed: {e}")


# =========================
# Entry point
# =========================

def parse_args():
    parser = argparse.ArgumentParser(
        description="Real-time speech-to-text using ffmpeg + faster-whisper on Windows"
    )
    parser.add_argument(
        "--list-devices", action="store_true",
        help="List available DirectShow audio devices and exit"
    )
    parser.add_argument(
        "--device", "-d", type=str, default=None,
        help='DirectShow audio device name (e.g. "Stereo Mix (Realtek(R) Audio)")'
    )
    parser.add_argument(
        "--model", "-m", type=str, default=DEFAULT_MODEL,
        choices=["tiny", "tiny.en", "base", "base.en", "small", "small.en",
                 "medium", "medium.en", "large-v1", "large-v2", "large-v3"],
        help=f"Whisper model size (default: {DEFAULT_MODEL})"
    )
    parser.add_argument(
        "--language", "-l", type=str, default=DEFAULT_LANGUAGE,
        help='Language code, e.g. "en", "es", or "auto" for detection (default: en)'
    )
    parser.add_argument(
        "--chunk", type=float, default=DEFAULT_CHUNK_SECONDS,
        help=f"Audio chunk size in seconds (default: {DEFAULT_CHUNK_SECONDS})"
    )
    parser.add_argument(
        "--overlap", type=float, default=DEFAULT_OVERLAP_SECONDS,
        help=f"Overlap between chunks in seconds (default: {DEFAULT_OVERLAP_SECONDS})"
    )
    parser.add_argument(
        "--output", "-o", type=str, default=OUTPUT_FILE,
        help=f"Transcript output file (default: {OUTPUT_FILE})"
    )
    parser.add_argument(
        "--cpu", action="store_true",
        help="Force CPU even if a GPU is available"
    )
    return parser.parse_args()


def main():
    args = parse_args()

    if args.list_devices:
        list_audio_devices()
        return

    if not args.device:
        print("[ERROR] No audio device specified.")
        print("Run with --list-devices to see available devices, then pass one with --device.\n")
        print('Example:')
        print('  python main.py --list-devices')
        print('  python main.py --device "Stereo Mix (Realtek(R) Audio)"\n')
        sys.exit(1)

    if args.cpu:
        device, compute_type = "cpu", "int8"
        print("[INFO] Forced CPU mode.")
    else:
        device, compute_type = detect_device()

    chunk_bytes = int(SAMPLE_RATE * args.chunk) * BYTES_PER_SAMPLE
    overlap_bytes = int(SAMPLE_RATE * args.overlap) * BYTES_PER_SAMPLE

    audio_queue = queue.Queue()
    stop_event = threading.Event()

    process = start_ffmpeg(args.device)

    threads = [
        threading.Thread(target=ffmpeg_error_reader, args=(process, stop_event), daemon=True),
        threading.Thread(target=audio_reader, args=(process, audio_queue, stop_event, chunk_bytes, overlap_bytes), daemon=True),
        threading.Thread(target=transcriber, args=(audio_queue, stop_event, args.model, device, compute_type, args.language, args.output), daemon=True),
    ]
    for t in threads:
        t.start()

    try:
        while not stop_event.is_set():
            time.sleep(0.5)
            if process.poll() is not None:
                print("[ERROR] FFmpeg process exited unexpectedly.")
                stop_event.set()
                break
    except KeyboardInterrupt:
        print("\n[INFO] Stopping...")
        stop_event.set()
    finally:
        try:
            process.terminate()
            process.wait(timeout=5)
        except Exception:
            process.kill()
        print(f"[INFO] Done. Transcript saved to: {args.output}")


if __name__ == "__main__":
    main()
