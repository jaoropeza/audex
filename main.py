import os
import queue
import sys
import re
import argparse
import threading
import time
import warnings
from datetime import datetime
from pathlib import Path

# ── Warning / logging suppression (unchanged) ─────────────────────────────────
warnings.filterwarnings("ignore", message=".*weights_only.*", category=FutureWarning)
warnings.filterwarnings("ignore", message=".*pkg_resources.*", category=DeprecationWarning)
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
os.environ.setdefault("TORCH_CUDNN_V8_API_DISABLED", "0")


# Compatibility shim: pyannote.audio 3.x uses removed use_auth_token kwarg
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

# ── Constants ─────────────────────────────────────────────────────────────────
SAMPLE_RATE      = 16000
CHANNELS         = 1
BYTES_PER_SAMPLE = 2
DEFAULT_MODEL    = "small"
DEFAULT_LANGUAGE = "en"
DEFAULT_CHUNK_SECONDS   = 5
DEFAULT_OVERLAP_SECONDS = 1
OUTPUT_PREFIX    = "transcript"


# ── AudioSaver ────────────────────────────────────────────────────────────────

class AudioSaver:
    """Thread-safe PCM accumulator; writes WAV on save()."""

    def __init__(self, path: str):
        self.path  = path
        self._lock = threading.Lock()
        self._buf  = bytearray()

    def write(self, pcm_bytes: bytes):
        with self._lock:
            self._buf.extend(pcm_bytes)

    def save(self):
        import wave
        if not self._buf:
            print("[INFO] No audio recorded — skipping audio file.")
            return
        with wave.open(self.path, "wb") as wf:
            wf.setnchannels(CHANNELS)
            wf.setsampwidth(BYTES_PER_SAMPLE)
            wf.setframerate(SAMPLE_RATE)
            wf.writeframes(bytes(self._buf))
        size_mb    = len(self._buf) / (1024 * 1024)
        duration_s = len(self._buf) / (SAMPLE_RATE * BYTES_PER_SAMPLE * CHANNELS)
        print(f"[INFO] Audio saved to: {self.path} ({duration_s:.0f}s, {size_mb:.1f} MB)")


# ── SpeakerTracker ────────────────────────────────────────────────────────────

class SpeakerTracker:
    def __init__(self, similarity_threshold=0.75):
        self.profiles  = {}
        self.named     = set()
        self.threshold = similarity_threshold
        self._counter  = 0

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


# ── Device discovery ──────────────────────────────────────────────────────────

def list_dshow_devices():
    import subprocess
    try:
        subprocess.run(["ffmpeg", "-version"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except FileNotFoundError:
        print("[ERROR] ffmpeg not found.")
        return []
    result = subprocess.run(
        ["ffmpeg", "-list_devices", "true", "-f", "dshow", "-i", "dummy"],
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
        print("[ERROR] pyaudiowpatch not installed.")
        return []
    p       = pyaudio.PyAudio()
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


# ── Diarization helpers ───────────────────────────────────────────────────────

def _emb_to_numpy(emb) -> np.ndarray:
    if isinstance(emb, np.ndarray):
        return emb.squeeze().astype(np.float32)
    return emb.squeeze().cpu().numpy().astype(np.float32)


def load_diarization_models(hf_token: str, torch_device: str):
    from pyannote.audio import Pipeline, Inference
    from huggingface_hub import login
    import torch

    login(token=hf_token, add_to_git_credential=False)
    print("[INFO] Loading diarization pipeline on CPU…", flush=True)
    original = os.environ.get("CUDA_VISIBLE_DEVICES")
    os.environ["CUDA_VISIBLE_DEVICES"] = ""
    try:
        pipeline = Pipeline.from_pretrained("pyannote/speaker-diarization-3.1")
        pipeline.to(torch.device("cpu"))
        print("[INFO] Loading speaker embedding model…", flush=True)
        embedding_model = Inference("pyannote/embedding", window="whole")
        embedding_model.to(torch.device("cpu"))
    finally:
        if original is None:
            os.environ.pop("CUDA_VISIBLE_DEVICES", None)
        else:
            os.environ["CUDA_VISIBLE_DEVICES"] = original
    print(f"[INFO] Diarization models ready (faster-whisper uses {torch_device}).")
    return pipeline, embedding_model


def load_speaker_profiles(profiles_dir: str, embedding_model, tracker: SpeakerTracker):
    import torch
    try:
        import soundfile as sf
    except ImportError:
        print("[WARN] soundfile not installed — skipping speaker profiles.")
        return
    for wav_path in sorted(Path(profiles_dir).glob("*.wav")):
        name      = wav_path.stem
        audio, sr = sf.read(str(wav_path), dtype="float32")
        if audio.ndim > 1:
            audio = audio.mean(axis=1)
        if sr != SAMPLE_RATE:
            target_len = int(len(audio) * SAMPLE_RATE / sr)
            indices    = np.linspace(0, len(audio) - 1, target_len)
            audio      = np.interp(indices, np.arange(len(audio)), audio).astype(np.float32)
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


# ── Transcript helpers ────────────────────────────────────────────────────────

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


# ── Transcription loops ───────────────────────────────────────────────────────

def _plain_transcription_loop(stt_adapter, audio_queue, stop_event, language, output_file):
    """Run in a daemon thread; delegates chunk processing to the STT adapter."""
    while not stop_event.is_set():
        try:
            label, raw_audio = audio_queue.get(timeout=1)
        except queue.Empty:
            continue
        line = stt_adapter.transcribe_chunk(label, raw_audio, language)
        if line:
            print(line)
            append_transcript(line, output_file)


def _diarized_transcription_loop(
    stt_adapter, audio_queue, stop_event, language, output_file,
    diarization_pipeline, embedding_model, speaker_tracker, num_speakers=None
):
    """Diarization loop: uses stt_adapter.transcribe_segments() + pyannote."""
    import collections as _col
    import torch
    from adapters.stt.faster_whisper_adapter import (
        _clean_text, _is_hallucination, _strip_prefix_overlap,
    )

    MIN_TURN_SECONDS = 0.5
    recent_texts     = _col.deque(maxlen=3)
    last_words: list = []

    def flush(spk, words, label):
        nonlocal last_words
        text  = _strip_prefix_overlap(" ".join(words).strip(), last_words)
        clean = _clean_text(text)
        if _is_hallucination(text, recent_texts):
            recent_texts.append(clean)
            return
        recent_texts.append(clean)
        last_words = (last_words + text.split())[-20:]
        ts   = datetime.now().strftime("%H:%M:%S")
        line = _format_line(ts, label, spk, text)
        print(line)
        append_transcript(line, output_file)

    while not stop_event.is_set():
        try:
            label, raw_audio = audio_queue.get(timeout=1)
        except queue.Empty:
            continue

        arr = np.frombuffer(raw_audio, dtype=np.int16).astype(np.float32) / 32768.0
        if arr.size == 0 or float(np.sqrt(np.mean(arr ** 2))) < 0.003:
            continue

        segments = stt_adapter.transcribe_segments(raw_audio, language)
        if not segments:
            continue

        try:
            waveform      = torch.from_numpy(arr).unsqueeze(0).float()
            diarize_kwargs = {"min_speakers": 1, "max_speakers": num_speakers} if num_speakers else {}
            diarization   = diarization_pipeline(
                {"waveform": waveform, "sample_rate": SAMPLE_RATE},
                **diarize_kwargs,
            )
            speaker_turns = []
            for turn, _, _ in diarization.itertracks(yield_label=True):
                if (turn.end - turn.start) < MIN_TURN_SECONDS:
                    continue
                s = int(turn.start * SAMPLE_RATE)
                e = int(turn.end * SAMPLE_RATE)
                turn_audio = arr[s:e]
                if turn_audio.size == 0:
                    continue
                tw = torch.from_numpy(turn_audio).unsqueeze(0).float()
                with torch.no_grad():
                    emb = embedding_model({"waveform": tw, "sample_rate": SAMPLE_RATE})
                resolved = speaker_tracker.match(_emb_to_numpy(emb))
                speaker_turns.append((turn.start, turn.end, resolved))
        except Exception as exc:
            print(f"[ERROR] Diarization failed: {exc}")
            continue

        current_speaker, current_words = None, []
        for seg in segments:
            words = seg.words if seg.words else []
            if not words:
                spk = _get_speaker_at(speaker_turns, seg.start, seg.end)
                if spk != current_speaker:
                    flush(current_speaker, current_words, label)
                    current_speaker, current_words = spk, []
                current_words.append(seg.text.strip())
                continue
            for word in words:
                spk = _get_speaker_at(speaker_turns, word.start, word.end)
                if spk != current_speaker:
                    flush(current_speaker, current_words, label)
                    current_speaker, current_words = spk, []
                current_words.append(word.word.strip())
        flush(current_speaker, current_words, label)


# ── DI wiring helpers ─────────────────────────────────────────────────────────

def _pick_stt_adapter(args, saved_stt_config):
    """Build STT adapter: CLI flags (model/language) override saved config."""
    from application.stt_service import STTService
    from domain.entities import STTConfig, STTProvider

    # CLI --model / --language always win
    config = STTConfig(
        provider = saved_stt_config.provider,
        model    = args.model if args.model != DEFAULT_MODEL else saved_stt_config.model,
        language = args.language if args.language != DEFAULT_LANGUAGE else saved_stt_config.language,
        api_url  = saved_stt_config.api_url,
        api_key  = saved_stt_config.api_key,
    )
    return STTService(config).get_adapter()


def _pick_audio_adapter(args):
    """Return the appropriate AudioCapturePort based on CLI flags."""
    from adapters.audio.wasapi_loopback_adapter import WASAPILoopbackAdapter
    from adapters.audio.dshow_mic_adapter import DShowMicAdapter
    from adapters.audio.merge_adapter import MergeAdapter

    if args.merge:
        return MergeAdapter(mic_device=args.mic, loopback_hint=args.device)
    elif args.loopback:
        return WASAPILoopbackAdapter(device_hint=args.device)
    else:
        return DShowMicAdapter(device_name=args.device, debug=args.debug_audio)


# ── run_recording ─────────────────────────────────────────────────────────────

def run_recording(stt_adapter, audio_adapter, output_path, args, audio_saver, summarizer):
    audio_queue = queue.Queue()
    stop_event  = threading.Event()
    threads     = []

    # Audio capture thread
    threads.append(threading.Thread(
        target=audio_adapter.stream,
        kwargs=dict(
            audio_queue=audio_queue,
            stop_event=stop_event,
            chunk_seconds=args.chunk,
            overlap_seconds=args.overlap,
            debug=args.debug_audio,
            audio_saver=audio_saver,
        ),
        daemon=True,
    ))

    # Transcription thread
    if args.diarize:
        hf_token = args.hf_token or os.environ.get("HF_TOKEN")
        if not hf_token:
            print("[ERROR] Diarization requires a HuggingFace token.")
            sys.exit(1)
        torch_device = "cuda" if _has_cuda() else "cpu"
        pipeline, embedding_model = load_diarization_models(hf_token, torch_device)
        tracker = SpeakerTracker(similarity_threshold=0.75)
        if args.speaker_profiles:
            load_speaker_profiles(args.speaker_profiles, embedding_model, tracker)
        threads.append(threading.Thread(
            target=_diarized_transcription_loop,
            args=(stt_adapter, audio_queue, stop_event, args.language, output_path,
                  pipeline, embedding_model, tracker, args.num_speakers),
            daemon=True,
        ))
    else:
        threads.append(threading.Thread(
            target=_plain_transcription_loop,
            args=(stt_adapter, audio_queue, stop_event, args.language, output_path),
            daemon=True,
        ))

    for t in threads:
        t.start()

    try:
        while not stop_event.is_set():
            time.sleep(0.5)
    except KeyboardInterrupt:
        print("\n[INFO] Stopping…")
        stop_event.set()
    finally:
        audio_adapter.close()
        print(f"[INFO] Done. Transcript saved to: {output_path}")
        if audio_saver:
            audio_saver.save()
        if summarizer:
            summarizer.summarize(output_path)


def _has_cuda() -> bool:
    try:
        import ctranslate2
        return ctranslate2.get_cuda_device_count() > 0
    except Exception:
        return False


# ── CLI ───────────────────────────────────────────────────────────────────────

def _make_output_path(name_or_prefix: str) -> str:
    p    = Path(name_or_prefix)
    stem = p.stem if p.suffix.lower() == ".txt" else p.name
    ts   = datetime.now().strftime("%Y%m%d_%H%M%S")
    return str(p.parent / f"{stem}_{ts}.txt")


def parse_args():
    parser = argparse.ArgumentParser(
        description="Real-time speech-to-text with optional speaker diarization on Windows"
    )
    parser.add_argument("--list-devices", action="store_true")
    parser.add_argument("--device", "-d", type=str, default=None)
    parser.add_argument("--loopback", action="store_true")
    parser.add_argument("--merge", action="store_true")
    parser.add_argument("--mic", type=str, default=None)
    parser.add_argument("--model", "-m", type=str, default=DEFAULT_MODEL,
                        choices=["tiny","tiny.en","base","base.en","small","small.en",
                                 "medium","medium.en","large-v1","large-v2","large-v3"])
    parser.add_argument("--language", "-l", type=str, default=DEFAULT_LANGUAGE)
    parser.add_argument("--diarize", action="store_true")
    parser.add_argument("--hf-token", type=str, default=None)
    parser.add_argument("--num-speakers", type=int, default=None)
    parser.add_argument("--speaker-profiles", type=str, default=None)
    parser.add_argument("--chunk", type=float, default=DEFAULT_CHUNK_SECONDS)
    parser.add_argument("--overlap", type=float, default=DEFAULT_OVERLAP_SECONDS)
    parser.add_argument("--output", "-o", type=str, default=OUTPUT_PREFIX)
    parser.add_argument("--cpu", action="store_true")
    parser.add_argument("--debug-audio", action="store_true")
    parser.add_argument("--save-audio", nargs="?", const="audio", metavar="PREFIX")
    parser.add_argument("--summarize", action="store_true")
    parser.add_argument("--api-key", type=str, default=None)
    return parser.parse_args()


def main():
    args = parse_args()

    if args.list_devices:
        list_audio_devices()
        return

    if args.merge and not args.mic:
        print("[ERROR] --merge requires --mic <microphone device name>.")
        sys.exit(1)

    if not args.loopback and not args.merge and not args.device:
        print("[ERROR] No audio device specified. Run --list-devices to see options.")
        sys.exit(1)

    # Load saved config; CLI args for model/language take precedence
    from application.config_service import ConfigService
    saved_cfg = ConfigService().get()

    stt_adapter   = _pick_stt_adapter(args, saved_cfg.stt)
    audio_adapter = _pick_audio_adapter(args)

    output_path = _make_output_path(args.output)
    print(f"[INFO] Transcript will be saved to: {output_path}")

    audio_saver = None
    if args.save_audio is not None:
        audio_path  = _make_output_path(args.save_audio).replace(".txt", ".wav")
        audio_saver = AudioSaver(audio_path)
        print(f"[INFO] Audio will be saved to: {audio_path}")

    summarizer = None
    if args.summarize:
        from adapters.summarization.claude_summarizer_adapter import ClaudeSummarizerAdapter
        summarizer = ClaudeSummarizerAdapter(api_key=args.api_key)

    run_recording(stt_adapter, audio_adapter, output_path, args, audio_saver, summarizer)


if __name__ == "__main__":
    main()
