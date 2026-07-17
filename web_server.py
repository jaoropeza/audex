import asyncio
import logging
import os
import sys
from pathlib import Path

# Windows requires ProactorEventLoop for asyncio subprocess support
if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())

# ── Configurable logging ──────────────────────────────────────────────────────
# Set LOG_LEVEL=DEBUG / INFO / WARNING / ERROR in the environment to control
# verbosity. Defaults to INFO.
_LOG_LEVEL = os.environ.get("LOG_LEVEL", "INFO").upper()
logging.basicConfig(
    level=getattr(logging, _LOG_LEVEL, logging.INFO),
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("stt")

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from api import transcripts, stream, recording, translate, config as config_api, db as db_api
from api import auth as auth_api
from api import categories as categories_api
from api import admin as admin_api
from api import speakers as speakers_api

TAGS_METADATA = [
    {"name": "auth",        "description": "Authentication — register, login, token validation"},
    {"name": "transcripts", "description": "Transcript CRUD — list, read, delete, search, tags, audio"},
    {"name": "recording",   "description": "Recording session — start, stop, status, device list"},
    {"name": "stream",      "description": "SSE — live transcript tail and recording log"},
    {"name": "translate",   "description": "Translation — batch line or grouped translation"},
    {"name": "categories",  "description": "Category management — create, assign to transcripts"},
    {"name": "config",      "description": "Provider configuration — STT, translation, summary, embeddings"},
    {"name": "db",          "description": "Database — semantic search, indexing status"},
    {"name": "admin",       "description": "Administration — user management, system stats, global settings"},
    {"name": "speakers",    "description": "Speaker profiles — named voice samples for diarization"},
]

app = FastAPI(
    title="STT Web UI",
    version="2.0.0",
    description=(
        "Speech-to-text web application with multi-user support, "
        "real-time transcription, translation, summarization, and semantic search.\n\n"
        "All endpoints except `/api/auth/*` require a JWT bearer token "
        "obtained from `POST /api/auth/login`."
    ),
    openapi_tags=TAGS_METADATA,
    docs_url="/docs",
    redoc_url="/redoc",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173",
                   "http://localhost:8000", "http://127.0.0.1:8000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["Authorization", "Content-Type", "*"],
)


@app.on_event("startup")
async def on_startup():
    logger.info("STT server starting (log level: %s)", _LOG_LEVEL)
    try:
        from application.db_service import startup_index
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, startup_index)
        logger.info("DB startup index complete")
    except Exception as exc:
        logger.warning("DB startup index failed: %s", exc)


app.include_router(auth_api.router,     prefix="/api/auth",        tags=["auth"])
app.include_router(transcripts.router,  prefix="/api/transcripts", tags=["transcripts"])
app.include_router(stream.router,       prefix="/api/stream",      tags=["stream"])
app.include_router(recording.router,    prefix="/api/recording",   tags=["recording"])
app.include_router(translate.router,    prefix="/api",             tags=["translate"])
app.include_router(config_api.router,   prefix="/api",             tags=["config"])
app.include_router(db_api.router,       prefix="/api/db",          tags=["db"])
app.include_router(categories_api.router, prefix="/api",            tags=["categories"])
app.include_router(admin_api.router,      prefix="/api/admin",       tags=["admin"])
app.include_router(speakers_api.router,   prefix="/api/speakers",    tags=["speakers"])

# Serve React build. Must be registered AFTER API routes.
_static = Path(__file__).parent / "frontend" / "dist"
if _static.exists():
    app.mount("/", StaticFiles(directory=str(_static), html=True), name="static")
else:
    from fastapi.responses import JSONResponse

    @app.get("/")
    async def no_build():
        return JSONResponse(
            {"error": "Frontend not built yet. Run: cd frontend && npm install && npm run build"},
            status_code=503,
        )

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("web_server:app", host="127.0.0.1", port=8000, reload=True)
