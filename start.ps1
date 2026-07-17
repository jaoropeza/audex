# STT Web App — startup script (PowerShell)

$ErrorActionPreference = "Stop"
$Root = $PSScriptRoot

# ── helpers ───────────────────────────────────────────────────────────────────

function Write-Step { param($msg) Write-Host "`n>> $msg" -ForegroundColor Cyan }
function Write-OK   { param($msg) Write-Host "   OK  $msg" -ForegroundColor Green }
function Write-Warn { param($msg) Write-Host "   !!  $msg" -ForegroundColor Yellow }
function Write-Err  { param($msg) Write-Host "   XX  $msg" -ForegroundColor Red }

# ── 0. Pre-flight checks ──────────────────────────────────────────────────────

Write-Step "Pre-flight checks"

# Python 3.11+
$pyver = & python --version 2>&1
if ($LASTEXITCODE -ne 0) {
    Write-Err "python not found — install Python 3.11 and add it to PATH"
    exit 1
}
$pyMinor = [int]($pyver -replace '.*3\.(\d+).*','$1')
if ($pyMinor -lt 11) {
    Write-Err "Python 3.11+ required (found: $pyver)"
    exit 1
}
Write-OK $pyver

# Node.js (only needed if we have to build)
$nodeAvailable = $null -ne (Get-Command node -ErrorAction SilentlyContinue)
if (-not $nodeAvailable) {
    Write-Warn "node not found — frontend builds will be skipped (pre-built dist/ must already exist)"
}

# ffmpeg
if ($null -eq (Get-Command ffmpeg -ErrorAction SilentlyContinue)) {
    Write-Warn "ffmpeg not found in PATH — audio recording will not work"
    Write-Warn "Download the full-shared build from gyan.dev/ffmpeg/builds and add bin\ to PATH"
} else {
    Write-OK "ffmpeg found"
}

# STT_SECRET_KEY warning
$secretKey = $env:STT_SECRET_KEY
if (-not $secretKey -or $secretKey -eq "change-me-in-production-please") {
    Write-Warn "STT_SECRET_KEY is not set — using the insecure default"
    Write-Warn "Set it before starting: `$env:STT_SECRET_KEY = 'a-long-random-secret'"
}

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

$Dist        = Join-Path $Root "frontend\dist"
$FrontendDir = Join-Path $Root "frontend"

if (-not (Test-Path $Dist)) {
    if (-not $nodeAvailable) {
        Write-Err "No dist/ found and node is not installed — cannot build frontend"
        Write-Err "Install Node.js 18+ from nodejs.org, then re-run this script"
        exit 1
    }
    Write-Warn "No dist/ found — building frontend..."
    Push-Location $FrontendDir
    npm install --silent
    npm run build
    Pop-Location
    Write-OK "Frontend built"
} else {
    Write-OK "dist/ present (run 'cd frontend && npm run build' to rebuild after source changes)"
}

# ── 4. Start server ───────────────────────────────────────────────────────────

Write-Step "Starting server"

$Host_ = "127.0.0.1"
$Port  = 8000
$Url   = "http://${Host_}:${Port}"

Write-Host ""
Write-Host "  $Url" -ForegroundColor White
Write-Host "  $Url/docs  — Swagger UI" -ForegroundColor DarkGray
Write-Host "  Press Ctrl+C to stop" -ForegroundColor DarkGray
Write-Host ""

# Open browser after a short delay so the server has time to start
Start-Job -ScriptBlock {
    param($url)
    Start-Sleep -Seconds 3
    Start-Process $url
} -ArgumentList $Url | Out-Null

Set-Location $Root
python -m uvicorn web_server:app --host $Host_ --port $Port --reload
