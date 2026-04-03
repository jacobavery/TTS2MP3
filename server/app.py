"""FastAPI application factory for TTS2MP3 Studio web."""

import asyncio
import json
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from engine.audio import check_ffmpeg, check_tesseract
from engine.cache import ensure_cache_dirs
from engine.voices import list_all_voices
from server.config import CACHE_DIR, FAVORITES_FILE, MAX_CONCURRENT_JOBS
from server.jobs import JobManager

# Global app state — shared across routes
app_state: dict = {}


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup: load voices, check tools. Shutdown: cleanup."""
    app_state["cache_dir"] = CACHE_DIR
    ensure_cache_dirs(CACHE_DIR)
    app_state["ffmpeg"] = check_ffmpeg()
    app_state["tesseract"] = check_tesseract()
    app_state["job_manager"] = JobManager(max_concurrent=MAX_CONCURRENT_JOBS)
    app_state["semaphore"] = asyncio.Semaphore(MAX_CONCURRENT_JOBS)

    # Load favorites
    try:
        with open(FAVORITES_FILE) as f:
            app_state["favorites"] = set(json.load(f))
    except (FileNotFoundError, json.JSONDecodeError):
        app_state["favorites"] = set()

    # Load voices
    try:
        voices = await list_all_voices(cache_dir=CACHE_DIR)
    except Exception:
        voices = []
    app_state["voices"] = voices

    # Background voice refresh every 30 minutes
    async def refresh_voices():
        while True:
            await asyncio.sleep(1800)
            try:
                app_state["voices"] = await list_all_voices(cache_dir=CACHE_DIR)
            except Exception:
                pass

    refresh_task = asyncio.create_task(refresh_voices())

    yield

    refresh_task.cancel()
    app_state["job_manager"].cleanup_expired()


app = FastAPI(title="TTS2MP3 Studio", lifespan=lifespan)

# CORS for local dev
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Routes
from server.routes.voices import router as voices_router
from server.routes.convert import router as convert_router
from server.routes.upload import router as upload_router
from server.routes.settings import router as settings_router
from server.routes.batch import router as batch_router
from server.routes.audiobook import router as audiobook_router
from server.routes.characters import router as characters_router
from server.routes.compare import router as compare_router
from server.routes.projects import router as projects_router

app.include_router(voices_router)
app.include_router(convert_router)
app.include_router(upload_router)
app.include_router(settings_router)
app.include_router(batch_router)
app.include_router(audiobook_router)
app.include_router(characters_router)
app.include_router(compare_router)
app.include_router(projects_router)

# Serve web app at /app/
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WEB_DIR = os.path.join(BASE_DIR, "web")
if os.path.isdir(WEB_DIR):
    app.mount("/app", StaticFiles(directory=WEB_DIR, html=True), name="web")
