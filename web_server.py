import asyncio
import sys
from pathlib import Path

# Windows requires ProactorEventLoop for asyncio subprocess support
if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from api import transcripts, stream, recording, translate, config as config_api, db as db_api

app = FastAPI(title="STT Web UI", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173",
                   "http://localhost:8000", "http://127.0.0.1:8000"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
async def on_startup():
    try:
        from application.db_service import startup_index
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, startup_index)
    except Exception as exc:
        print(f"[WARN] DB startup index failed: {exc}")


app.include_router(transcripts.router,  prefix="/api/transcripts", tags=["transcripts"])
app.include_router(stream.router,       prefix="/api/stream",       tags=["stream"])
app.include_router(recording.router,    prefix="/api/recording",    tags=["recording"])
app.include_router(translate.router,    prefix="/api",              tags=["translate"])
app.include_router(config_api.router,   prefix="/api",              tags=["config"])
app.include_router(db_api.router,       prefix="/api/db",           tags=["db"])

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
