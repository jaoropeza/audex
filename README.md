# Real-Time Speech-to-Text (STT)

Real-time transcription on Windows using [faster-whisper](https://github.com/SYSTRAN/faster-whisper) and [pyannote.audio](https://github.com/pyannote/pyannote-audio). Includes a full-featured web UI with multi-user support, translation, summarization, semantic search, and an admin panel.

---

## Requirements

| Requirement | Version |
|---|---|
| Python | 3.11 |
| Node.js | 18+ (for building the frontend) |
| ffmpeg | 7 or 8 (full-shared build on Windows) |
| NVIDIA GPU | Optional — RTX recommended for `large-v3` |
| CUDA driver | 12.x or 13.x |

### Install ffmpeg

Download the **full-shared** Windows build from [gyan.dev/ffmpeg/builds](https://www.gyan.dev/ffmpeg/builds/), extract it, and add the `bin\` folder to your system `PATH`. Verify:

```powershell
ffmpeg -version
```

---

## Quick Start — Web UI

The fastest way to start both the backend and the frontend:

```powershell
# PowerShell
.\start.ps1
```

```bash
# Bash / Git Bash
./start.sh
```

Both scripts will:

1. Create a Python virtual environment if one doesn't exist
2. Install all Python dependencies
3. Build the React frontend if `frontend/dist/` is missing
4. Start the server at `http://127.0.0.1:8000`

On first run the server prints a one-time admin password to the console:

```text
[STT] *** First-run setup: admin user created ***
[STT]     Username : admin
[STT]     Password : <random>
[STT]     Change this password via the Admin panel after first login.
```

Open `http://127.0.0.1:8000` in your browser and log in.

---

## Manual Installation

```powershell
# 1. Create and activate a virtual environment
python -m venv .venv
.venv\Scripts\Activate.ps1

# 2. Install Python dependencies
pip install -r requirements.txt

# 3. Install GPU-accelerated torch + torchaudio (same version, same CUDA index)
pip install torch==2.5.1 torchaudio==2.5.1 --index-url https://download.pytorch.org/whl/cu121

# 4. Build the frontend
cd frontend
npm install
npm run build
cd ..

# 5. Start the server
python web_server.py
```

> **CPU-only machines:** Skip step 3. The app falls back to CPU automatically. Transcription will be slower.

---

## Web UI Features

### Authentication & Multi-User

- JWT-based login (tokens valid for 7 days)
- First-run auto-creates an admin account (password printed once to the console)
- Each user has their own transcripts, tags, categories, and configuration
- Admin panel for user management and system stats

### Transcripts

- Live streaming via SSE while recording
- Full-text search within any transcript
- Tags for organizing transcripts
- Categories with colors for structured grouping
- Playback of paired audio recordings
- Download as `.txt`

### Translation

- Batch translation of transcript lines or time-grouped segments
- Configurable source and target language
- Custom prompt templates per translation
- Supports: Anthropic Claude, OpenAI, Ollama, Google Gemini

### Summarization

- AI-generated summary for any transcript
- Custom summary prompt templates
- Saved to the database, displayed inline

### Semantic Search

- Vector search across all transcripts (powered by ChromaDB)
- Configurable chunking strategy: Fixed lines / Speaker turn / Time window
- Results scoped to the current user

### Settings (per-user)

- STT provider: FasterWhisper (local), Parakeet-NIM, Parakeet-NeMo
- Translation provider: Anthropic, OpenAI, Ollama, Gemini
- Summary provider: Anthropic, OpenAI, Ollama, Gemini
- Embeddings: provider, model, API URL, chunk strategy, chunk size
- Settings are stored per-user in the database and fall back to the global `config/settings.json`

### Admin Panel

Accessible only to users with the `admin` role:

- List all users with transcript counts
- Create users, change roles, activate/deactivate accounts
- System statistics: user count, transcript count, database size, ChromaDB size, transcripts directory size
- View and update the global (default) provider configuration

---

## API Documentation

The REST API is documented with Swagger UI and ReDoc:

| URL | Description |
|---|---|
| `http://127.0.0.1:8000/docs` | Interactive Swagger UI — try endpoints directly |
| `http://127.0.0.1:8000/redoc` | ReDoc — clean reference layout |

All endpoints except `GET /api/auth/bootstrap-status`, `POST /api/auth/register` (first-run only), and `POST /api/auth/login` require a `Bearer` token in the `Authorization` header.

### Auth endpoints

| Method | Path | Description |
|---|---|---|
| `GET` | `/api/auth/bootstrap-status` | Returns `{needs_setup: true}` when no users exist |
| `POST` | `/api/auth/register` | Create the first admin account (first-run only) |
| `POST` | `/api/auth/login` | Login — returns `{access_token, user}` |
| `GET` | `/api/auth/me` | Current authenticated user |

### Transcript endpoints

| Method | Path | Description |
|---|---|---|
| `GET` | `/api/transcripts` | List all transcripts for the current user |
| `GET` | `/api/transcripts/{filename}` | Get transcript lines |
| `DELETE` | `/api/transcripts/{filename}` | Delete transcript |
| `GET` | `/api/transcripts/{filename}/search?q=` | Search within a transcript |
| `GET` | `/api/transcripts/{filename}/tags` | Get tags |
| `PUT` | `/api/transcripts/{filename}/tags` | Set tags |
| `GET` | `/api/transcripts/{filename}/audio` | Stream the paired audio file |
| `GET` | `/api/transcripts/{filename}/summary` | Get saved summary |
| `POST` | `/api/transcripts/{filename}/summarize` | Generate a new summary |
| `GET` | `/api/transcripts/{filename}/categories` | Get assigned categories |
| `PUT` | `/api/transcripts/{filename}/categories` | Assign categories |

### Category endpoints

| Method | Path | Description |
|---|---|---|
| `GET` | `/api/categories` | List user's categories |
| `POST` | `/api/categories` | Create a category |
| `PUT` | `/api/categories/{id}` | Update a category |
| `DELETE` | `/api/categories/{id}` | Delete a category |

### Recording endpoints

| Method | Path | Description |
|---|---|---|
| `GET` | `/api/recording/devices` | List available audio devices |
| `POST` | `/api/recording/start` | Start a recording session |
| `POST` | `/api/recording/stop` | Stop the session and index the transcript |
| `GET` | `/api/recording/status` | Current session status |
| `GET` | `/api/recording/log?token=` | SSE stream of process log lines |

### Stream endpoint

| Method | Path                             | Description                          |
| ------ | -------------------------------- | ------------------------------------ |
| `GET`  | `/api/stream/{filename}?token=`  | SSE stream of live transcript lines  |

> SSE endpoints use `?token=` instead of `Authorization:` because `EventSource` cannot send custom headers.

### Config endpoints

| Method | Path | Description |
|---|---|---|
| `GET` | `/api/config` | Get current user's provider config |
| `PUT` | `/api/config` | Save provider config |
| `POST` | `/api/config/test/stt` | Test STT provider connection |
| `POST` | `/api/config/test/translation` | Test translation provider |
| `POST` | `/api/config/test/summary` | Test summary provider |
| `POST` | `/api/config/reset` | Reset to global defaults |

### Translation & search

| Method | Path | Description |
|---|---|---|
| `POST` | `/api/translate` | Translate a batch of lines |
| `GET` | `/api/db/search?q=` | Semantic vector search |
| `GET` | `/api/db/transcriptions` | List all indexed transcriptions |

### Admin endpoints (admin role required)

| Method | Path | Description |
|---|---|---|
| `GET` | `/api/admin/users` | List all users |
| `POST` | `/api/admin/users` | Create a user |
| `PUT` | `/api/admin/users/{id}` | Update role / active status |
| `GET` | `/api/admin/stats` | System statistics |
| `GET` | `/api/admin/global-settings` | Global provider config |
| `PUT` | `/api/admin/global-settings` | Update global provider config |

---

## Environment Variables

| Variable | Default | Description |
|---|---|---|
| `STT_SECRET_KEY` | `change-me-in-production-please` | JWT signing secret — **change this in production** |
| `STT_DB_PATH` | `db/stt.db` | Path to the SQLite database |
| `STT_TRANSCRIPTS_DIR` | `transcripts/` | Root directory for transcript and audio files |
| `HF_TOKEN` | — | HuggingFace token for speaker diarization |

Set them in the shell before starting:

```powershell
$env:STT_SECRET_KEY = "a-long-random-secret"
python web_server.py
```

---

## Command-Line Interface

The CLI (`main.py`) can still be used independently of the web UI.

### Device selection

| Flag | Description |
|---|---|
| `--list-devices` | Print available microphone and loopback devices and exit |
| `--device NAME` | Microphone device name (from `--list-devices`) |
| `--loopback` | Capture speaker/headphone output via WASAPI loopback |
| `--merge` | Capture microphone **and** speakers simultaneously |
| `--mic NAME` | Microphone device name when using `--merge` |

### Whisper model

| Flag | Default | Description |
|---|---|---|
| `--model` / `-m` | `small` | Model size: `tiny`, `base`, `small`, `medium`, `large-v1`, `large-v2`, `large-v3` |
| `--language` / `-l` | `en` | Language code (`en`, `es`, `fr`, …) or `auto` |

### Speaker diarization

| Flag | Description |
|---|---|
| `--diarize` | Enable speaker diarization (requires HuggingFace token) |
| `--hf-token TOKEN` | HuggingFace access token (or set `HF_TOKEN` env var) |
| `--num-speakers N` | Hint for the expected number of speakers |
| `--speaker-profiles DIR` | Directory of `.wav` files for named speaker identification |

### Output

| Flag | Default | Description |
|---|---|---|
| `--output` / `-o` | `transcript.txt` | Output file path |
| `--save-audio` | — | Save the captured audio as a `.wav` file alongside the transcript |
| `--cpu` | — | Force CPU inference even if a GPU is available |
| `--debug-audio` | — | Print RMS level per chunk for diagnosing silence |

### CLI examples

```powershell
# Microphone
python main.py --device "Microphone (HyperX Quadcast)" --model large-v3 --language es

# Loopback (system audio)
python main.py --loopback --model large-v3

# Merge mode with diarization
python main.py --merge --mic "Microphone (HyperX Quadcast)" --model large-v3 --diarize --num-speakers 2
```

---

## Speaker Diarization Setup

1. Create a free account at [huggingface.co](https://huggingface.co)
2. Accept model terms on:
   - [pyannote/speaker-diarization-3.1](https://huggingface.co/pyannote/speaker-diarization-3.1)
   - [pyannote/segmentation-3.0](https://huggingface.co/pyannote/segmentation-3.0)
3. Generate a read token at [huggingface.co/settings/tokens](https://huggingface.co/settings/tokens)
4. Set the token: `$env:HF_TOKEN = "hf_your_token_here"`

Named speaker identification — record a few seconds of each speaker and save as `.wav`:

```shell
speakers/
  Alice.wav
  Bob.wav
```

```powershell
python main.py --loopback --model large-v3 --diarize --speaker-profiles ./speakers/
```

---

## Transcript Format

```log
[10:32:14] Hello, how are you?
[10:32:16][MIC] This is from the microphone.
[10:32:20][SPK][Alice] This is Alice speaking through the speakers.
```

---

## Running Tests

```powershell
# Python unit and integration tests
.venv\Scripts\python.exe -m pytest tests/ -v
```

Tests use isolated temporary SQLite databases and transcript directories — no production data is touched.

### Test structure

```shell
tests/
  conftest.py              — fixtures: tmp_db, client, admin_token, auth_headers, user_token
  unit/
    test_auth_service.py   — password hashing, JWT encode/decode
    test_sqlite_adapter.py — upsert, isolation, tags, summaries
    test_config_service.py — per-user config, fallback, reset
    test_chroma_chunking.py — LINES / SPEAKER_TURN / TIME_WINDOW strategies
  integration/
    test_auth_api.py       — bootstrap, register, login, /me
    test_admin_api.py      — user CRUD, stats, global settings
    test_regression.py     — all existing endpoints still work with auth
```

---

## Model Size Guide

| Model      | VRAM  | Speed    | Accuracy  | Best for      |
| ---------- | ----- | -------- | --------- | ------------- |
| `tiny`     | ~1 GB | Fastest  | Low       | Testing       |
| `base`     | ~1 GB | Fast     | Moderate  | Quick drafts  |
| `small`    | ~2 GB | Fast     | Good      | Default       |
| `medium`   | ~5 GB | Moderate | Very good | Balanced      |
| `large-v3` | ~6 GB | Slower   | Best      | Production    |

---

## Troubleshooting

### No audio / only silence

- Run with `--debug-audio` to see RMS levels. `-87 dB` means silence.
- For loopback: audio must be actively playing through the target device.
- Check Windows Sound → Recording → **Show Disabled Devices** → enable **Stereo Mix**.

### `ffmpeg not found`

Add ffmpeg to your PATH. Download the full-shared build from [gyan.dev/ffmpeg/builds](https://www.gyan.dev/ffmpeg/builds/).

### `Torch not compiled with CUDA enabled`

torch was installed as CPU-only. Reinstall:

```powershell
pip uninstall torch torchaudio -y
pip install torch==2.5.1 torchaudio==2.5.1 --index-url https://download.pytorch.org/whl/cu121
```

### `WinError 127` on torchaudio

torch and torchaudio versions mismatch. Install both from the same CUDA index at the same version.

### Login fails after server restart

Tokens are signed with `STT_SECRET_KEY`. If the key changes between restarts, all existing tokens are invalidated. Set a stable key in your environment.

### Frontend shows "not built yet"

```powershell
cd frontend
npm install
npm run build
```

admin
8plXuJyz19g9YZMJ