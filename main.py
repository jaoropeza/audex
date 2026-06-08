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

SILENCE_DB_THRESHOLD = -70.0
SILENCE_WARN_CHUNKS = 10


# =========================
# Audio device discovery
# =========================

def _ffmpeg_available():
    try:
        subprocess.run([FFMPEG_PATH, "-version"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return True
    except FileNotFoundError:
        print("[ERROR] ffmpeg not found. Install it and add it to your PATH.")
        return False


def list_dshow_devices():
    """Lists DirectShow audio INPUT devices (microphones, Stereo Mix, etc.)"""
    if not _ffmpeg_available():
        return []

    result = subprocess.run(
        [FFMPEG_PATH, "-list_devices", "true", "-f", "dshow", "-i", "dummy"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.PIPE,
    )
    output = result.stderr.decode(errors="ignore")
    devices = []

    for line in output.splitlines():
        m = re.search(r'"(.+?)"\s+\(audio\)', line)
        if m:
            devices.append(m.group(1))

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
                devices.append(m.group(1))

    return devices


def list_loopback_devices():
    """Lists WASAPI loopback devices (speaker outputs) via pyaudiowpatch."""
    try:
        import pyaudiowpatch as pyaudio
    except ImportError:
        print("[ERROR] pyaudiowpatch not installed. Run: pip install pyaudiowpatch")
        return []

    p = pyaudio.PyAudio()
    devices = list(p.get_loopback_device_info_generator())
    p.terminate()
    return devices


def list_audio_devices():
    print("\n--- Input devices (microphones) ---")
    print("Usage: python main.py --device \"<name>\"\n")
    dshow = list_dshow_devices()
    if dshow:
        for d in dshow:
            print(f'  "{d}"')
    else:
        print("  None found.")

    print("\n--- Loopback devices (speaker outputs — capture what is playing) ---")
    print("Usage: python main.py --loopback [--device \"<partial name>\"]\n")
    loopback = list_loopback_devices()
    if loopback:
        for dev in loopback:
            print(f'  "{dev["name"]}"')
    else:
        print("  None found (install pyaudiowpatch or run as Administrator).")

    print()
    return dshow, loopback


# =========================
# CUDA detection
# =========================

def detect_device():
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
# FFmpeg capture (microphone / dshow)
# =========================

def start_ffmpeg(audio_device, debug=False):
    command = [
        FFMPEG_PATH,
        "-hide_banner",
        "-loglevel", "warning" if debug else "error",
        "-f", "dshow",
        "-i", f"audio={audio_device}",
        "-ac", str(CHANNELS),
        "-ar", str(SAMPLE_RATE),
        "-fflags", "nobuffer",
        "-flags", "low_delay",
        "-f", "s16le",
        "-",
    ]
    print(f"[INFO] Starting microphone capture from: {audio_device}")
    try:
        process = subprocess.Popen(
            command,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            bufsize=0,
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


def audio_reader(process, audio_queue, stop_event, chunk_bytes, overlap_bytes, label="", debug=False):
    previous_overlap = b""
    chunk_count = 0
    silent_streak = 0

    while not stop_event.is_set():
        raw_chunk = process.stdout.read(chunk_bytes)
        if not raw_chunk:
            print("[WARN] FFmpeg stopped sending audio.")
            break

        chunk_count += 1
        arr = np.frombuffer(raw_chunk, dtype=np.int16).astype(np.float32)
        rms = float(np.sqrt(np.mean(arr ** 2))) if arr.size else 0.0
        db = 20 * np.log10(rms / 32768.0 + 1e-9)

        if db < SILENCE_DB_THRESHOLD:
            silent_streak += 1
            if silent_streak == SILENCE_WARN_CHUNKS:
                print(f"[WARN] Audio silent for {SILENCE_WARN_CHUNKS} chunks. Is the microphone active?")
        else:
            silent_streak = 0

        if debug:
            tag = f"{label} " if label else ""
            bar = "#" * int(max(0, (db + 60) / 2))
            print(f"[AUDIO {tag}] chunk={chunk_count:4d}  {db:6.1f} dB  |{bar:<30}|")

        audio_queue.put((label, previous_overlap + raw_chunk))
        previous_overlap = raw_chunk[-overlap_bytes:] if len(raw_chunk) >= overlap_bytes else raw_chunk

    stop_event.set()


# =========================
# WASAPI loopback capture (speakers)
# =========================

def loopback_reader(audio_queue, stop_event, device_name=None, chunk_seconds=DEFAULT_CHUNK_SECONDS,
                    overlap_seconds=DEFAULT_OVERLAP_SECONDS, label="", debug=False):
    """Captures speaker output via WASAPI loopback using pyaudiowpatch."""
    try:
        import pyaudiowpatch as pyaudio
    except ImportError:
        print("[ERROR] pyaudiowpatch not installed. Run: pip install pyaudiowpatch")
        stop_event.set()
        return

    p = pyaudio.PyAudio()

    # Find target loopback device
    target = None
    for dev in p.get_loopback_device_info_generator():
        if device_name is None or device_name.lower() in dev["name"].lower():
            target = dev
            break

    # Fall back to default output device loopback
    if target is None:
        try:
            wasapi_info = p.get_host_api_info_by_type(pyaudio.paWASAPI)
            default_out = p.get_device_info_by_index(wasapi_info["defaultOutputDevice"])
            for dev in p.get_loopback_device_info_generator():
                if default_out["name"] in dev["name"]:
                    target = dev
                    break
        except Exception:
            pass

    if target is None:
        print("[ERROR] No loopback device found. Run --list-devices to see available devices.")
        stop_event.set()
        p.terminate()
        return

    native_rate = int(target["defaultSampleRate"])
    native_channels = min(int(target["maxInputChannels"]), 2)
    print(f"[INFO] Loopback capture from: {target['name']} @ {native_rate} Hz / {native_channels} ch")

    target_chunk_bytes = int(SAMPLE_RATE * chunk_seconds) * BYTES_PER_SAMPLE
    overlap_bytes = int(SAMPLE_RATE * overlap_seconds) * BYTES_PER_SAMPLE
    frames_per_buffer = native_rate // 10  # 100 ms device chunks

    buffer = b""
    previous_overlap = b""
    chunk_count = 0
    silent_streak = 0

    def callback(in_data, _frame_count, _time_info, _status):
        nonlocal buffer, previous_overlap, chunk_count, silent_streak

        arr = np.frombuffer(in_data, dtype=np.int16).astype(np.float32)

        # Stereo → mono
        if native_channels == 2:
            arr = arr.reshape(-1, 2).mean(axis=1)

        # Resample to 16 kHz if needed
        if native_rate != SAMPLE_RATE:
            target_len = int(len(arr) * SAMPLE_RATE / native_rate)
            indices = np.linspace(0, len(arr) - 1, target_len)
            arr = np.interp(indices, np.arange(len(arr)), arr)

        buffer += arr.clip(-32768, 32767).astype(np.int16).tobytes()

        while len(buffer) >= target_chunk_bytes:
            chunk = buffer[:target_chunk_bytes]
            buffer = buffer[target_chunk_bytes:]
            chunk_count += 1

            chunk_arr = np.frombuffer(chunk, dtype=np.int16).astype(np.float32)
            rms = float(np.sqrt(np.mean(chunk_arr ** 2))) if chunk_arr.size else 0.0
            db = 20 * np.log10(rms / 32768.0 + 1e-9)

            if db < SILENCE_DB_THRESHOLD:
                silent_streak += 1
                if silent_streak == SILENCE_WARN_CHUNKS:
                    print(f"[WARN] Audio silent for {SILENCE_WARN_CHUNKS} chunks. Is audio playing?")
            else:
                silent_streak = 0

            if debug:
                tag = f"{label} " if label else ""
                bar = "#" * int(max(0, (db + 60) / 2))
                print(f"[AUDIO {tag}] chunk={chunk_count:4d}  {db:6.1f} dB  |{bar:<30}|")

            audio_queue.put((label, previous_overlap + chunk))
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
    stop_event.set()


# =========================
# Transcription
# =========================

def pcm_to_float32(raw_audio):
    arr = np.frombuffer(raw_audio, dtype=np.int16)
    if arr.size == 0:
        return None
    return arr.astype(np.float32) / 32768.0


def append_transcript(line, output_file):
    with open(output_file, "a", encoding="utf-8") as f:
        f.write(line + "\n")


def transcriber(audio_queue, stop_event, model_size, device, compute_type, language, output_file):
    print(f"[INFO] Loading Whisper model '{model_size}' on {device}/{compute_type}...")
    model = WhisperModel(model_size, device=device, compute_type=compute_type)
    print("[INFO] Model loaded. Listening... (Ctrl+C to stop)\n")

    while not stop_event.is_set():
        try:
            label, raw_audio = audio_queue.get(timeout=1)
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
                without_timestamps=True,
            )
            text = " ".join(s.text.strip() for s in segments if s.text.strip())
            if text:
                ts = datetime.now().strftime("%H:%M:%S")
                prefix = f"[{label}]" if label else ""
                line = f"[{ts}]{prefix} {text}"
                print(line)
                append_transcript(line, output_file)
        except Exception as e:
            print(f"[ERROR] Transcription failed: {e}")


# =========================
# Entry point
# =========================

def parse_args():
    parser = argparse.ArgumentParser(
        description="Real-time speech-to-text using faster-whisper on Windows"
    )
    parser.add_argument(
        "--list-devices", action="store_true",
        help="List available input and loopback devices and exit",
    )
    parser.add_argument(
        "--device", "-d", type=str, default=None,
        help="Device name (microphone name for dshow, or partial speaker name for --loopback)",
    )
    parser.add_argument(
        "--loopback", action="store_true",
        help="Capture speaker output (WASAPI loopback) instead of microphone. "
             "Omit --device to auto-select the default output device.",
    )
    parser.add_argument(
        "--merge", action="store_true",
        help="Capture both microphone and speakers simultaneously. "
             "Use --mic for the microphone device and --device for the speaker (optional).",
    )
    parser.add_argument(
        "--mic", type=str, default=None,
        help="Microphone device name for --merge mode.",
    )
    parser.add_argument(
        "--model", "-m", type=str, default=DEFAULT_MODEL,
        choices=["tiny", "tiny.en", "base", "base.en", "small", "small.en",
                 "medium", "medium.en", "large-v1", "large-v2", "large-v3"],
        help=f"Whisper model size (default: {DEFAULT_MODEL})",
    )
    parser.add_argument(
        "--language", "-l", type=str, default=DEFAULT_LANGUAGE,
        help='Language code e.g. "en", "es", or "auto" (default: en)',
    )
    parser.add_argument(
        "--chunk", type=float, default=DEFAULT_CHUNK_SECONDS,
        help=f"Audio chunk size in seconds (default: {DEFAULT_CHUNK_SECONDS})",
    )
    parser.add_argument(
        "--overlap", type=float, default=DEFAULT_OVERLAP_SECONDS,
        help=f"Overlap between chunks in seconds (default: {DEFAULT_OVERLAP_SECONDS})",
    )
    parser.add_argument(
        "--output", "-o", type=str, default=OUTPUT_FILE,
        help=f"Transcript output file (default: {OUTPUT_FILE})",
    )
    parser.add_argument(
        "--cpu", action="store_true",
        help="Force CPU even if a GPU is available",
    )
    parser.add_argument(
        "--debug-audio", action="store_true",
        help="Print RMS level of each audio chunk",
    )
    return parser.parse_args()


def main():
    args = parse_args()

    if args.list_devices:
        list_audio_devices()
        return

    if args.merge and not args.mic:
        print("[ERROR] --merge requires --mic <microphone device name>.")
        print('Example: python main.py --merge --mic "Microphone (HyperX Quadcast)"\n')
        sys.exit(1)

    if not args.loopback and not args.merge and not args.device:
        print("[ERROR] No audio device specified.")
        print("Run --list-devices to see available devices.\n")
        print("Examples:")
        print('  python main.py --device "Microphone (HyperX Quadcast)"        # mic only')
        print('  python main.py --loopback                                      # speakers only')
        print('  python main.py --merge --mic "Microphone (HyperX Quadcast)"   # both\n')
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
    threads = []
    process = None

    if args.merge:
        # Both microphone and speaker loopback, labeled separately
        process = start_ffmpeg(args.mic, debug=args.debug_audio)
        threads.append(threading.Thread(target=ffmpeg_error_reader, args=(process, stop_event), daemon=True))
        threads.append(threading.Thread(
            target=audio_reader,
            args=(process, audio_queue, stop_event, chunk_bytes, overlap_bytes, "MIC", args.debug_audio),
            daemon=True,
        ))
        threads.append(threading.Thread(
            target=loopback_reader,
            args=(audio_queue, stop_event, args.device, args.chunk, args.overlap, "SPK", args.debug_audio),
            daemon=True,
        ))
    elif args.loopback:
        threads.append(threading.Thread(
            target=loopback_reader,
            args=(audio_queue, stop_event, args.device, args.chunk, args.overlap, "", args.debug_audio),
            daemon=True,
        ))
    else:
        process = start_ffmpeg(args.device, debug=args.debug_audio)
        threads.append(threading.Thread(target=ffmpeg_error_reader, args=(process, stop_event), daemon=True))
        threads.append(threading.Thread(
            target=audio_reader,
            args=(process, audio_queue, stop_event, chunk_bytes, overlap_bytes, "", args.debug_audio),
            daemon=True,
        ))

    threads.append(threading.Thread(
        target=transcriber,
        args=(audio_queue, stop_event, args.model, device, compute_type, args.language, args.output),
        daemon=True,
    ))

    for t in threads:
        t.start()

    try:
        while not stop_event.is_set():
            time.sleep(0.5)
            if process and process.poll() is not None:
                print("[ERROR] FFmpeg process exited unexpectedly.")
                stop_event.set()
                break
    except KeyboardInterrupt:
        print("\n[INFO] Stopping...")
        stop_event.set()
    finally:
        if process:
            try:
                process.terminate()
                process.wait(timeout=5)
            except Exception:
                process.kill()
        print(f"[INFO] Done. Transcript saved to: {args.output}")


if __name__ == "__main__":
    main()
