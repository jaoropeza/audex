# STT Web App — startup script (PowerShell)

$ErrorActionPreference = "Stop"
$Root = $PSScriptRoot

# ── helpers ───────────────────────────────────────────────────────────────────

function Write-Step { param($msg) Write-Host "`n>> $msg" -ForegroundColor Cyan }
function Write-OK   { param($msg) Write-Host "   $msg" -ForegroundColor Green }
function Write-Warn { param($msg) Write-Host "   $msg" -ForegroundColor Yellow }
function Write-Err  { param($msg) Write-Host "   $msg" -ForegroundColor Red }

# ── 1. Python venv ────────────────────────────────────────────────────────────

Write-Step "Python environment"

$VenvDir = Join-Path $Root ".venv"
if (-not (Test-Path $VenvDir)) {
    Write-Warn ".venv not found — creating..."
    python -m venv $VenvDir
}

$Activate = Join-Path $VenvDir "Scripts\Activate.ps1"
. $Activate
Write-OK "Activated: $VenvDir"

# ── 2. Python dependencies ────────────────────────────────────────────────────

Write-Step "Python dependencies"

$Req = Join-Path $Root "requirements.txt"
pip install -q -r $Req --disable-pip-version-check
Write-OK "requirements.txt installed"

# ── 3. Frontend build ─────────────────────────────────────────────────────────

Write-Step "Frontend"

$Dist = Join-Path $Root "frontend\dist"
$FrontendDir = Join-Path $Root "frontend"

if (-not (Test-Path $Dist)) {
    Write-Warn "No dist/ found — building frontend..."
    Push-Location $FrontendDir
    npm install --silent
    npm run build
    Pop-Location
    Write-OK "Frontend built"
} else {
    Write-OK "dist/ already present — skipping build (run 'npm run build' manually to update)"
}

# ── 4. Start server ───────────────────────────────────────────────────────────

Write-Step "Starting server"

$Host_ = "127.0.0.1"
$Port  = 8000
$Url   = "http://${Host_}:${Port}"

Write-Host ""
Write-Host "  $Url" -ForegroundColor White
Write-Host "  Press Ctrl+C to stop" -ForegroundColor DarkGray
Write-Host ""

Set-Location $Root
python -m uvicorn web_server:app --host $Host_ --port $Port --reload
