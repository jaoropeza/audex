import os
import subprocess
import queue
import threading
import time
import sys
import re
import argparse
import warnings
from datetime import datetime
from pathlib import Path

# Suppress torch.load pickle warning — models loaded from HuggingFace Hub are trusted
warnings.filterwarnings("ignore", message=".*weights_only.*", category=FutureWarning)
warnings.filterwarnings("ignore", message=".*pkg_resources.*", category=DeprecationWarning)
# Suppress pytorch_lightning / pyannote version-mismatch and checkpoint-upgrade chatter
warnings.filterwarnings("ignore", message=".*ModelCheckpoint.*callback states.*")
warnings.filterwarnings("ignore", message=".*Found keys that are not in the model state dict.*")
warnings.filterwarnings("ignore", message=".*Model was trained with.*")
warnings.filterwarnings("ignore", message=".*std\\(\\).*degrees of freedom.*", category=UserWarning)
warnings.filterwarnings("ignore", message=".*detected number of speakers.*", category=UserWarning)

import logging as _logging
_logging.getLogger("pytorch_lightning").setLevel(_logging.ERROR)
_logging.getLogger("lightning_fabric").setLevel(_logging.ERROR)
_logging.getLogger("lightning").setLevel(_logging.ERROR)

os.environ.setdefault("HF_HUB_DISABLE_SYMLINKS_WARNING", "1")
# Prefer torch's own bundled cuDNN over any system-installed version to avoid DLL symbol conflicts
os.environ.setdefault("TORCH_CUDNN_V8_API_DISABLED", "0")

# Compatibility shim: pyannote.audio 3.x calls hf_hub_download(use_auth_token=...)
# which was removed in huggingface_hub 0.25+. Patch it to translate to token=...
def _patch_huggingface_hub():
    try:
        import huggingface_hub
        for fn_name in ("hf_hub_download", "snapshot_download"):
            original = getattr(huggingface_hub, fn_name)
            def _make_patched(orig):
                def patched(*args, **kwargs):
                    if "use_auth_token" in kwargs:
                        token = kwargs.pop("use_auth_token")
                        if token and "token" not in kwargs:
                            kwargs["token"] = token
                    return orig(*args, **kwargs)
                return patched
            setattr(huggingface_hub, fn_name, _make_patched(original))
    except Exception:
        pass

_patch_huggingface_hub()

import numpy as np
from faster_whisper import WhisperModel


# =========================
# Defaults
# =========================

FFMPEG_PATH = "ffmpeg"
SAMPLE_RATE = 16000
CHANNELS = 1
BYTES_PER_SAMPLE = 2

DEFAULT_MODEL = "small"
DEFAULT_LANGUAGE = "en"
DEFAULT_CHUNK_SECONDS = 5
DEFAULT_OVERLAP_SECONDS = 1
OUTPUT_PREFIX = "transcript"

SILENCE_DB_THRESHOLD = -70.0
SILENCE_WARN_CHUNKS = 10


# =========================
# Speaker tracking
# =========================

class SpeakerTracker:
    """
    Matches speaker embeddings across audio chunks.
    Named profiles (loaded from .wav files) are fixed references.
    Auto-discovered speakers get IDs like SPEAKER_00, SPEAKER_01, …
    """

    def __init__(self, similarity_threshold=0.75):
        self.profiles = {}        # name -> normalized embedding (np.ndarray)
        self.named = set()        # names loaded from profiles (not updated)
        self.threshold = similarity_threshold
        self._counter = 0

    def add_named_profile(self, name: str, embedding: np.ndarray):
        self.profiles[name] = self._norm(embedding)
        self.named.add(name)

    def match(self, embedding: np.ndarray) -> str:
        emb = self._norm(embedding)
        best_name, best_sim = None, -1.0
        for name, ref in self.profiles.items():
            sim = float(np.dot(emb, ref))
            if sim > best_sim:
                best_sim, best_name = sim, name

        if best_name and best_sim >= self.threshold:
            # Update running mean only for auto-discovered speakers
            if best_name not in self.named:
                updated = 0.9 * self.profiles[best_name] + 0.1 * emb
                self.profiles[best_name] = self._norm(updated)
            return best_name

        name = f"SPEAKER_{self._counter:02d}"
        self._counter += 1
        self.profiles[name] = emb.copy()
        return name

    @staticmethod
    def _norm(v: np.ndarray) -> np.ndarray:
        n = np.linalg.norm(v)
        return v / (n + 1e-9)


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
    if not _ffmpeg_available():
        return []
    result = subprocess.run(
        [FFMPEG_PATH, "-list_devices", "true", "-f", "dshow", "-i", "dummy"],
        stdout=subprocess.DEVNULL, stderr=subprocess.PIPE,
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
    for d in list_dshow_devices():
        print(f'  "{d}"')

    print("\n--- Loopback devices (speakers) ---")
    print("Usage: python main.py --loopback [--device \"<partial name>\"]\n")
    loopback = list_loopback_devices()
    if loopback:
        for dev in loopback:
            print(f'  "{dev["name"]}"')
    else:
        print("  None found.")
    print()


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
# FFmpeg capture (microphone)
# =========================

def start_ffmpeg(audio_device, debug=False):
    command = [
        FFMPEG_PATH, "-hide_banner",
        "-loglevel", "warning" if debug else "error",
        "-f", "dshow",
        "-i", f"audio={audio_device}",
        "-ac", str(CHANNELS),
        "-ar", str(SAMPLE_RATE),
        "-fflags", "nobuffer",
        "-flags", "low_delay",
        "-f", "s16le", "-",
    ]
    print(f"[INFO] Starting microphone capture from: {audio_device}")
    try:
        process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, bufsize=0)
    except FileNotFoundError:
        print("[ERROR] ffmpeg not found.")
        sys.exit(1)
    return process


def ffmpeg_error_reader(process, stop_event):
    while not stop_event.is_set():
        line = process.stderr.readline()
        if not line:
            break
        msg = line.decode(errors="ignore").strip()
        if msg:
            print(f"[FFMPEG] {msg}")


def _rms_db(raw: bytes) -> float:
    arr = np.frombuffer(raw, dtype=np.int16).astype(np.float32)
    rms = float(np.sqrt(np.mean(arr ** 2))) if arr.size else 0.0
    return 20 * np.log10(rms / 32768.0 + 1e-9)


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
        previous_overlap = raw_chunk[-overlap_bytes:] if len(raw_chunk) >= overlap_bytes else raw_chunk

    stop_event.set()


# =========================
# WASAPI loopback capture (speakers)
# =========================

def loopback_reader(audio_queue, stop_event, device_name=None, chunk_seconds=DEFAULT_CHUNK_SECONDS,
                    overlap_seconds=DEFAULT_OVERLAP_SECONDS, label="", debug=False):
    try:
        import pyaudiowpatch as pyaudio
    except ImportError:
        print("[ERROR] pyaudiowpatch not installed. Run: pip install pyaudiowpatch")
        stop_event.set()
        return

    p = pyaudio.PyAudio()
    target = None
    for dev in p.get_loopback_device_info_generator():
        if device_name is None or device_name.lower() in dev["name"].lower():
            target = dev
            break

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
        print("[ERROR] No loopback device found. Run --list-devices.")
        stop_event.set()
        p.terminate()
        return

    native_rate = int(target["defaultSampleRate"])
    native_channels = min(int(target["maxInputChannels"]), 2)
    print(f"[INFO] Loopback capture from: {target['name']} @ {native_rate} Hz / {native_channels} ch")

    target_chunk_bytes = int(SAMPLE_RATE * chunk_seconds) * BYTES_PER_SAMPLE
    overlap_bytes = int(SAMPLE_RATE * overlap_seconds) * BYTES_PER_SAMPLE
    frames_per_buffer = native_rate // 10

    buf = b""
    previous_overlap = b""
    chunk_count = 0
    silent_streak = 0

    def callback(in_data, _fc, _ti, _st):
        nonlocal buf, previous_overlap, chunk_count, silent_streak

        arr = np.frombuffer(in_data, dtype=np.int16).astype(np.float32)
        if native_channels == 2:
            arr = arr.reshape(-1, 2).mean(axis=1)
        if native_rate != SAMPLE_RATE:
            target_len = int(len(arr) * SAMPLE_RATE / native_rate)
            indices = np.linspace(0, len(arr) - 1, target_len)
            arr = np.interp(indices, np.arange(len(arr)), arr)

        buf += arr.clip(-32768, 32767).astype(np.int16).tobytes()

        while len(buf) >= target_chunk_bytes:
            chunk = buf[:target_chunk_bytes]
            buf = buf[target_chunk_bytes:]
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
# Diarization helpers
# =========================

def load_diarization_models(hf_token: str, torch_device: str):
    from pyannote.audio import Pipeline, Inference
    from huggingface_hub import login
    import torch

    login(token=hf_token, add_to_git_credential=False)

    # pyannote is loaded on CPU unconditionally.
    # Pipeline.from_pretrained() internally auto-detects CUDA and initialises cuDNN,
    # which causes a fatal cuDNN symbol error on some Windows setups even when
    # torch.cuda.is_available() returns True (DLL conflict between bundled and system cuDNN).
    # Faster-whisper (via CTranslate2) is unaffected and continues to run on the GPU.
    # CPU diarization of 5-second chunks is fast enough for real-time use.
    diarize_device = "cpu"

    print("[INFO] Loading diarization pipeline on CPU (models cached locally)...", flush=True)
    # Temporarily mask the GPU so pyannote never attempts CUDA initialisation
    original = os.environ.get("CUDA_VISIBLE_DEVICES")
    os.environ["CUDA_VISIBLE_DEVICES"] = ""
    try:
        pipeline = Pipeline.from_pretrained("pyannote/speaker-diarization-3.1")
        pipeline.to(torch.device(diarize_device))
        print("[INFO] Loading speaker embedding model...", flush=True)
        embedding_model = Inference("pyannote/embedding", window="whole")
        embedding_model.to(torch.device(diarize_device))
    finally:
        # Always restore GPU visibility for faster-whisper / ctranslate2
        if original is None:
            os.environ.pop("CUDA_VISIBLE_DEVICES", None)
        else:
            os.environ["CUDA_VISIBLE_DEVICES"] = original

    print(f"[INFO] Diarization models ready on {diarize_device} (faster-whisper uses {torch_device}).")
    return pipeline, embedding_model


def _emb_to_numpy(emb) -> np.ndarray:
    """Return embedding as a flat numpy float32 array regardless of source type."""
    if isinstance(emb, np.ndarray):
        return emb.squeeze().astype(np.float32)
    return emb.squeeze().cpu().numpy().astype(np.float32)


def load_speaker_profiles(profiles_dir: str, embedding_model, tracker: SpeakerTracker):
    import torch
    try:
        import soundfile as sf
    except ImportError:
        print("[WARN] soundfile not installed — skipping speaker profiles. pip install soundfile")
        return

    for wav_path in sorted(Path(profiles_dir).glob("*.wav")):
        name = wav_path.stem
        audio, sr = sf.read(str(wav_path), dtype="float32")
        if audio.ndim > 1:
            audio = audio.mean(axis=1)
        if sr != SAMPLE_RATE:
            target_len = int(len(audio) * SAMPLE_RATE / sr)
            indices = np.linspace(0, len(audio) - 1, target_len)
            audio = np.interp(indices, np.arange(len(audio)), audio).astype(np.float32)

        waveform = torch.from_numpy(audio).unsqueeze(0).float()
        with torch.no_grad():
            emb = embedding_model({"waveform": waveform, "sample_rate": SAMPLE_RATE})
        tracker.add_named_profile(name, _emb_to_numpy(emb))
        print(f"[INFO] Speaker profile loaded: {name}")


def _get_speaker_at(turns, start: float, end: float) -> str:
    best_name, best_overlap = "UNKNOWN", 0.0
    for t_start, t_end, name in turns:
        overlap = max(0.0, min(t_end, end) - max(t_start, start))
        if overlap > best_overlap:
            best_overlap, best_name = overlap, name
    return best_name


# =========================
# Transcription (plain)
# =========================

def pcm_to_float32(raw_audio: bytes):
    arr = np.frombuffer(raw_audio, dtype=np.int16)
    if arr.size == 0:
        return None
    return arr.astype(np.float32) / 32768.0


def append_transcript(line: str, output_file: str):
    with open(output_file, "a", encoding="utf-8") as f:
        f.write(line + "\n")


def _format_line(ts: str, label: str, speaker: str, text: str) -> str:
    parts = [f"[{ts}]"]
    if label:
        parts.append(f"[{label}]")
    if speaker:
        parts.append(f"[{speaker}]")
    parts.append(" " + text)
    return "".join(parts)


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
                line = _format_line(ts, label, "", text)
                print(line)
                append_transcript(line, output_file)
        except Exception as e:
            print(f"[ERROR] Transcription failed: {e}")


# =========================
# Transcription + diarization
# =========================

def transcriber_with_diarization(audio_queue, stop_event, model_size, device, compute_type,
                                  language, output_file, diarization_pipeline,
                                  embedding_model, speaker_tracker, num_speakers=None):
    import torch

    print(f"[INFO] Loading Whisper model '{model_size}' on {device}/{compute_type}...")
    model = WhisperModel(model_size, device=device, compute_type=compute_type)
    print("[INFO] Models ready. Listening with diarization... (Ctrl+C to stop)\n")

    MIN_TURN_SECONDS = 0.5

    while not stop_event.is_set():
        try:
            label, raw_audio = audio_queue.get(timeout=1)
        except queue.Empty:
            continue

        audio = pcm_to_float32(raw_audio)
        if audio is None:
            continue

        try:
            # 1. Transcribe with word-level timestamps
            segments, _ = model.transcribe(
                audio,
                language=language if language != "auto" else None,
                beam_size=1,
                vad_filter=True,
                condition_on_previous_text=False,
                word_timestamps=True,
            )
            segments = list(segments)
            if not segments:
                continue

            # 2. Diarize the chunk
            waveform = torch.from_numpy(audio).unsqueeze(0).float()
            # Use num_speakers as a soft maximum so pyannote doesn't complain
            # when a short chunk contains fewer active speakers than the hint.
            diarize_kwargs = {"min_speakers": 1, "max_speakers": num_speakers} if num_speakers else {}
            diarization = diarization_pipeline(
                {"waveform": waveform, "sample_rate": SAMPLE_RATE},
                **diarize_kwargs,
            )

            # 3. Extract embedding per speaker turn → resolve to tracker name
            speaker_turns = []
            for turn, _, _ in diarization.itertracks(yield_label=True):
                if (turn.end - turn.start) < MIN_TURN_SECONDS:
                    continue
                s = int(turn.start * SAMPLE_RATE)
                e = int(turn.end * SAMPLE_RATE)
                turn_audio = audio[s:e]
                if turn_audio.size == 0:
                    continue
                turn_waveform = torch.from_numpy(turn_audio).unsqueeze(0).float()
                with torch.no_grad():
                    emb = embedding_model({"waveform": turn_waveform, "sample_rate": SAMPLE_RATE})
                resolved = speaker_tracker.match(_emb_to_numpy(emb))
                speaker_turns.append((turn.start, turn.end, resolved))

            # 4. Align transcription words to speaker turns, group by speaker
            current_speaker = None
            current_words = []

            def flush(spk, words):
                text = " ".join(words).strip()
                if text:
                    ts = datetime.now().strftime("%H:%M:%S")
                    line = _format_line(ts, label, spk, text)
                    print(line)
                    append_transcript(line, output_file)

            for seg in segments:
                words = seg.words if seg.words else []
                if not words:
                    spk = _get_speaker_at(speaker_turns, seg.start, seg.end)
                    if spk != current_speaker:
                        flush(current_speaker, current_words)
                        current_speaker, current_words = spk, []
                    current_words.append(seg.text.strip())
                    continue

                for word in words:
                    spk = _get_speaker_at(speaker_turns, word.start, word.end)
                    if spk != current_speaker:
                        flush(current_speaker, current_words)
                        current_speaker, current_words = spk, []
                    current_words.append(word.word.strip())

            flush(current_speaker, current_words)

        except Exception as e:
            print(f"[ERROR] Transcription/diarization failed: {e}")


# =========================
# Entry point
# =========================

def parse_args():
    parser = argparse.ArgumentParser(
        description="Real-time speech-to-text with optional speaker diarization on Windows"
    )
    # Device selection
    parser.add_argument("--list-devices", action="store_true",
                        help="List available input and loopback devices and exit")
    parser.add_argument("--device", "-d", type=str, default=None,
                        help="Microphone device name (dshow) or loopback device hint")
    parser.add_argument("--loopback", action="store_true",
                        help="Capture speaker output via WASAPI loopback")
    parser.add_argument("--merge", action="store_true",
                        help="Capture both microphone and speakers simultaneously")
    parser.add_argument("--mic", type=str, default=None,
                        help="Microphone device name for --merge mode")

    # Whisper
    parser.add_argument("--model", "-m", type=str, default=DEFAULT_MODEL,
                        choices=["tiny", "tiny.en", "base", "base.en", "small", "small.en",
                                 "medium", "medium.en", "large-v1", "large-v2", "large-v3"],
                        help=f"Whisper model size (default: {DEFAULT_MODEL})")
    parser.add_argument("--language", "-l", type=str, default=DEFAULT_LANGUAGE,
                        help='Language code e.g. "en", "es", or "auto" (default: en)')

    # Diarization
    parser.add_argument("--diarize", action="store_true",
                        help="Enable speaker diarization (requires pyannote.audio and HF token)")
    parser.add_argument("--hf-token", type=str, default=None,
                        help="HuggingFace token for pyannote models (or set HF_TOKEN env var)")
    parser.add_argument("--num-speakers", type=int, default=None,
                        help="Expected number of speakers (optional hint, 1-10)")
    parser.add_argument("--speaker-profiles", type=str, default=None,
                        help="Directory of .wav files for named speaker identification "
                             "(filename = speaker name, e.g. Alice.wav)")

    # Audio tuning
    parser.add_argument("--chunk", type=float, default=DEFAULT_CHUNK_SECONDS,
                        help=f"Audio chunk size in seconds (default: {DEFAULT_CHUNK_SECONDS})")
    parser.add_argument("--overlap", type=float, default=DEFAULT_OVERLAP_SECONDS,
                        help=f"Overlap between chunks in seconds (default: {DEFAULT_OVERLAP_SECONDS})")

    # Output / misc
    parser.add_argument("--output", "-o", type=str, default=OUTPUT_PREFIX,
                        help=(
                            f"Transcript file name or prefix (default: '{OUTPUT_PREFIX}'). "
                            "A timestamp is always appended, e.g. transcript_20260612_175830.txt"
                        ))
    parser.add_argument("--cpu", action="store_true",
                        help="Force CPU even if a GPU is available")
    parser.add_argument("--debug-audio", action="store_true",
                        help="Print RMS level of each audio chunk")
    return parser.parse_args()


def _make_output_path(name_or_prefix: str) -> str:
    """Return a timestamped output path, e.g. 'meeting_20260612_175830.txt'."""
    p = Path(name_or_prefix)
    stem = p.stem if p.suffix.lower() == ".txt" else p.name
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    return str(p.parent / f"{stem}_{ts}.txt")


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
        print("[ERROR] No audio device specified. Run --list-devices to see options.\n")
        print("Examples:")
        print('  python main.py --device "Microphone (HyperX Quadcast)"')
        print('  python main.py --loopback')
        print('  python main.py --merge --mic "Microphone (HyperX Quadcast)"')
        print('  python main.py --device "Microphone (HyperX Quadcast)" --diarize\n')
        sys.exit(1)

    args.output = _make_output_path(args.output)
    print(f"[INFO] Transcript will be saved to: {args.output}")

    # GPU/CPU
    if args.cpu:
        whisper_device, compute_type = "cpu", "int8"
        torch_device = "cpu"
        print("[INFO] Forced CPU mode.")
    else:
        whisper_device, compute_type = detect_device()
        torch_device = "cuda" if whisper_device == "cuda" else "cpu"

    chunk_bytes = int(SAMPLE_RATE * args.chunk) * BYTES_PER_SAMPLE
    overlap_bytes = int(SAMPLE_RATE * args.overlap) * BYTES_PER_SAMPLE

    audio_queue = queue.Queue()
    stop_event = threading.Event()
    threads = []
    process = None

    # --- Audio capture threads ---
    if args.merge:
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

    # --- Transcription thread ---
    if args.diarize:
        hf_token = args.hf_token or os.environ.get("HF_TOKEN")
        if not hf_token:
            print("[ERROR] Diarization requires a HuggingFace token.")
            print("  Set it with --hf-token YOUR_TOKEN or the HF_TOKEN environment variable.")
            print("  Get a token at https://huggingface.co/settings/tokens")
            print("  Then accept model terms at:")
            print("    https://huggingface.co/pyannote/speaker-diarization-3.1")
            print("    https://huggingface.co/pyannote/segmentation-3.0")
            sys.exit(1)

        diarization_pipeline, embedding_model = load_diarization_models(hf_token, torch_device)

        tracker = SpeakerTracker(similarity_threshold=0.75)
        if args.speaker_profiles:
            load_speaker_profiles(args.speaker_profiles, embedding_model, tracker)

        threads.append(threading.Thread(
            target=transcriber_with_diarization,
            args=(audio_queue, stop_event, args.model, whisper_device, compute_type,
                  args.language, args.output, diarization_pipeline, embedding_model,
                  tracker, args.num_speakers),
            daemon=True,
        ))
    else:
        threads.append(threading.Thread(
            target=transcriber,
            args=(audio_queue, stop_event, args.model, whisper_device, compute_type,
                  args.language, args.output),
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
