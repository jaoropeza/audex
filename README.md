# Real-Time Speech-to-Text (STT)

Real-time transcription on Windows using [faster-whisper](https://github.com/SYSTRAN/faster-whisper) and [pyannote.audio](https://github.com/pyannote/pyannote-audio). Supports microphone input, system audio (speaker loopback), simultaneous capture of both, and optional speaker diarization.

---

## Requirements

| Requirement | Version |
|---|---|
| Python | 3.11 |
| ffmpeg | 7 or 8 (full-shared build on Windows) |
| NVIDIA GPU | Optional — RTX recommended for `large-v3` |
| CUDA driver | 12.x or 13.x |

### Install ffmpeg

Download the **full-shared** Windows build from [gyan.dev/ffmpeg/builds](https://www.gyan.dev/ffmpeg/builds/), extract it, and add the `bin\` folder to your system `PATH`. Verify:

```powershell
ffmpeg -version
```

---

## Installation

```powershell
# 1. Create and activate a virtual environment
python -m venv .venv
.venv\Scripts\Activate.ps1

# 2. Install Python dependencies
pip install -r requirements.txt

# 3. Install GPU-accelerated torch + torchaudio (MUST use the same version from the same index)
pip install torch==2.5.1 torchaudio==2.5.1 --index-url https://download.pytorch.org/whl/cu121

# 4. Verify GPU is detected
python -c "import torch, torchaudio; print(torch.__version__, torch.cuda.is_available())"
# Expected: 2.5.1+cu121  True
```

> **CPU-only machines:** Skip step 3. The app falls back to CPU automatically (`int8` compute type). Transcription will be slower.

---

## Quick Start

```powershell
# List available audio devices
python main.py --list-devices

# Transcribe your microphone
python main.py --device "Microphone (HyperX Quadcast)" --model large-v3

# Transcribe system audio (whatever is playing through your speakers)
python main.py --loopback --model large-v3

# Transcribe both microphone and speakers at once
python main.py --merge --mic "Microphone (HyperX Quadcast)" --model large-v3
```

---

## All CLI Options

### Device selection

| Flag | Description |
|---|---|
| `--list-devices` | Print available microphone and loopback devices and exit |
| `--device NAME` | Microphone device name (from `--list-devices`) |
| `--loopback` | Capture speaker/headphone output via WASAPI loopback |
| `--merge` | Capture microphone **and** speakers simultaneously (labels output `[MIC]` / `[SPK]`) |
| `--mic NAME` | Microphone device name when using `--merge` |

### Whisper model

| Flag | Default | Description |
|---|---|---|
| `--model` / `-m` | `small` | Model size: `tiny`, `base`, `small`, `medium`, `large-v1`, `large-v2`, `large-v3` |
| `--language` / `-l` | `en` | Language code (`en`, `es`, `fr`, …) or `auto` for auto-detection |

### Speaker diarization

| Flag | Description |
|---|---|
| `--diarize` | Enable speaker diarization (requires HuggingFace token) |
| `--hf-token TOKEN` | HuggingFace access token (or set `HF_TOKEN` env var) |
| `--num-speakers N` | Optional hint for the expected number of speakers (improves accuracy) |
| `--speaker-profiles DIR` | Directory of `.wav` files for named speaker identification |

### Audio tuning

| Flag | Default | Description |
|---|---|---|
| `--chunk SECONDS` | `5` | Audio chunk size sent to Whisper |
| `--overlap SECONDS` | `1` | Overlap between consecutive chunks (improves continuity) |

### Output

| Flag | Default | Description |
|---|---|---|
| `--output` / `-o` | `transcript.txt` | File where the transcript is appended |
| `--cpu` | — | Force CPU inference even if a GPU is available |
| `--debug-audio` | — | Print RMS level and dB bar for each audio chunk |

---

## Usage Examples

### Microphone only

```powershell
python main.py --device "Microphone (HyperX Quadcast)" --model large-v3 --language en
```

### Speaker loopback (system audio)

Captures everything playing through your default output device (YouTube, calls, media players, etc.).

```powershell
# Default output device
python main.py --loopback --model large-v3

# Specific output device (partial name match)
python main.py --loopback --device "Headphones" --model large-v3
```

### Merge — microphone + speakers simultaneously

Both sources are transcribed by the same model instance. Output is labeled `[MIC]` and `[SPK]`.

```powershell
python main.py --merge --mic "Microphone (HyperX Quadcast)" --model large-v3

# Specify which speaker device to capture
python main.py --merge --mic "Microphone (HyperX Quadcast)" --device "Headphones" --model large-v3
```

Example output:
```
[10:32:14][MIC] Can you hear me?
[10:32:16][SPK] Yes, loud and clear.
[10:32:19][MIC] Great, let's get started.
```

### Spanish transcription

```powershell
python main.py --device "Microphone (HyperX Quadcast)" --model large-v3 --language es
```

### CPU-only mode

```powershell
python main.py --device "Microphone (HyperX Quadcast)" --model small --cpu
```

### Save transcript to a custom file

```powershell
python main.py --device "Microphone (HyperX Quadcast)" --model large-v3 --output meeting_2026.txt
```

### Debug audio levels

Use this to diagnose silence or device issues. Prints an RMS bar for every chunk.

```powershell
python main.py --device "Microphone (HyperX Quadcast)" --model large-v3 --debug-audio
```

---

## Speaker Diarization

Diarization identifies **who spoke when**. It requires a free HuggingFace account and accepting model terms.

### One-time setup

1. Create a free account at [huggingface.co](https://huggingface.co)
2. Accept model terms (click **Agree** on each page):
   - [pyannote/speaker-diarization-3.1](https://huggingface.co/pyannote/speaker-diarization-3.1)
   - [pyannote/segmentation-3.0](https://huggingface.co/pyannote/segmentation-3.0)
3. Create a read token at [huggingface.co/settings/tokens](https://huggingface.co/settings/tokens)
4. Store it in `.env` (never commit this file):

```
HF_TOKEN=hf_your_token_here
```

5. Load it before running:

```powershell
$env:HF_TOKEN = (Get-Content .env | Select-String "HF_TOKEN").ToString().Split("=")[1]
```

### Basic diarization

Speakers are auto-labeled `SPEAKER_00`, `SPEAKER_01`, etc.

```powershell
python main.py --device "Microphone (HyperX Quadcast)" --model large-v3 --diarize
```

### With speaker count hint

Providing the number of speakers improves accuracy significantly.

```powershell
python main.py --loopback --model large-v3 --diarize --num-speakers 2
```

### Named speaker identification

Record a few seconds of each person speaking and save them as `.wav` files named after the speaker:

```
speakers/
  Alice.wav
  Bob.wav
  Charlie.wav
```

```powershell
python main.py --loopback --model large-v3 --diarize --speaker-profiles ./speakers/
```

Output:
```
[10:32:14][Alice] Good morning everyone.
[10:32:18][Bob] Morning! Let's get started.
[10:32:22][Alice] First item on the agenda...
```

### Diarization + merge mode

```powershell
python main.py --merge --mic "Microphone (HyperX Quadcast)" --model large-v3 --diarize --num-speakers 3
```

Output combines both source labels and speaker labels:
```
[10:32:14][MIC][SPEAKER_00] Can everyone hear me?
[10:32:17][SPK][SPEAKER_01] Yes, we can hear you.
[10:32:20][SPK][SPEAKER_02] Same here.
```

---

## Model Size Guide

| Model | VRAM | Speed | Accuracy | Best for |
|---|---|---|---|---|
| `tiny` | ~1 GB | Fastest | Low | Testing |
| `base` | ~1 GB | Fast | Moderate | Quick drafts |
| `small` | ~2 GB | Fast | Good | Default |
| `medium` | ~5 GB | Moderate | Very good | Balanced |
| `large-v3` | ~6 GB | Slower | Best | Production |

> With an RTX 4060 (8 GB VRAM), `large-v3` is recommended.

---

## Transcript File Format

All output is appended to the transcript file with timestamps:

```
[10:32:14] Hello, how are you?
[10:32:16][MIC] This is from the microphone.
[10:32:20][SPK][Alice] This is Alice speaking through the speakers.
```

---

## Troubleshooting

### No audio / only silence detected

- Run with `--debug-audio` to see RMS levels per chunk.
- `-87 dB` means silence — nothing is playing or the wrong device is selected.
- For loopback: make sure audio is actively playing through the target device.
- Check Windows Sound settings → Recording tab → right-click → **Show Disabled Devices** → ensure **Stereo Mix** is enabled.

### `ffmpeg not found`

Add ffmpeg to your PATH. Download the full-shared build from [gyan.dev/ffmpeg/builds](https://www.gyan.dev/ffmpeg/builds/).

### `Torch not compiled with CUDA enabled`

torch was installed as CPU-only. Reinstall:

```powershell
pip uninstall torch torchaudio -y
pip install torch==2.5.1 torchaudio==2.5.1 --index-url https://download.pytorch.org/whl/cu121
```

### `WinError 127` on torchaudio

torch and torchaudio versions are mismatched. They must be the **same version** installed from the **same CUDA index**:

```powershell
pip install torch==2.5.1 torchaudio==2.5.1 --index-url https://download.pytorch.org/whl/cu121
```

### `use_auth_token` error from pyannote

Update pyannote to 3.x and use the `HF_TOKEN` environment variable instead:

```powershell
pip install "pyannote.audio>=3.1,<4.0"
$env:HF_TOKEN = "hf_your_token"
```

### `Pipeline.from_pretrained` fails / 401 Unauthorized

- Ensure you accepted the model terms on HuggingFace for both `pyannote/speaker-diarization-3.1` and `pyannote/segmentation-3.0`.
- Verify your token is valid at [huggingface.co/settings/tokens](https://huggingface.co/settings/tokens).

### GPU shows as `unknown GPU`

torch is CPU-only even though ctranslate2 detected a GPU. Reinstall torch with CUDA (see above).
