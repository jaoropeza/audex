#!/usr/bin/env bash
# STT Web App — startup script (bash)

set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# ── helpers ───────────────────────────────────────────────────────────────────

step() { printf "\n\033[0;36m>> %s\033[0m\n" "$*"; }
ok()   { printf "   \033[0;32m%s\033[0m\n"  "$*"; }
warn() { printf "   \033[0;33m%s\033[0m\n"  "$*"; }

# ── 1. Python venv ────────────────────────────────────────────────────────────

step "Python environment"

VENV="$ROOT/.venv"
if [[ ! -d "$VENV" ]]; then
    warn ".venv not found — creating..."
    python3 -m venv "$VENV"
fi

# shellcheck disable=SC1091
source "$VENV/bin/activate"
ok "Activated: $VENV"

# ── 2. Python dependencies ────────────────────────────────────────────────────

step "Python dependencies"

pip install -q -r "$ROOT/requirements.txt" --disable-pip-version-check
ok "requirements.txt installed"

# ── 3. Frontend build ─────────────────────────────────────────────────────────

step "Frontend"

DIST="$ROOT/frontend/dist"
if [[ ! -d "$DIST" ]]; then
    warn "No dist/ found — building frontend..."
    cd "$ROOT/frontend"
    npm install --silent
    npm run build
    cd "$ROOT"
    ok "Frontend built"
else
    ok "dist/ already present — skipping build (run 'npm run build' manually to update)"
fi

# ── 4. Start server ───────────────────────────────────────────────────────────

step "Starting server"

HOST="127.0.0.1"
PORT=8000

printf "\n  \033[1mhttp://%s:%s\033[0m\n" "$HOST" "$PORT"
printf "  Press Ctrl+C to stop\n\n"

cd "$ROOT"
python -m uvicorn web_server:app --host "$HOST" --port "$PORT" --reload
