"""Settings, favorites, history, and pronunciation routes."""

import json
import os

from fastapi import APIRouter, HTTPException

from engine.audio import check_ffmpeg, check_tesseract
from engine.cache import cache_size
from server.config import (
    FAVORITES_FILE, HISTORY_FILE, PRONUNCIATION_FILE, SETTINGS_FILE,
)
from server.models import (
    FavoriteToggle, FavoritesUpdate, HistoryRecord, PronunciationEntry,
    SettingsUpdate, SystemStatus,
)

router = APIRouter(prefix="/api", tags=["settings"])


# ── Helpers ──────────────────────────────────────────────────────

def _read_json(path, default=None):
    try:
        with open(path) as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return default if default is not None else {}


def _write_json(path, data):
    with open(path, "w") as f:
        json.dump(data, f, indent=2)


# ── Settings ─────────────────────────────────────────────────────

@router.get("/settings")
async def get_settings():
    return {"settings": _read_json(SETTINGS_FILE, {})}


@router.put("/settings")
async def update_settings(body: SettingsUpdate):
    current = _read_json(SETTINGS_FILE, {})
    current.update(body.settings)
    _write_json(SETTINGS_FILE, current)
    return {"ok": True}


# ── Favorites ────────────────────────────────────────────────────

@router.get("/favorites")
async def get_favorites():
    favs = _read_json(FAVORITES_FILE, [])
    return {"favorites": favs}


@router.put("/favorites")
async def update_favorites(body: FavoritesUpdate):
    _write_json(FAVORITES_FILE, body.favorites)
    from server.app import app_state
    app_state["favorites"] = set(body.favorites)
    return {"ok": True}


@router.post("/favorites/toggle")
async def toggle_favorite(body: FavoriteToggle):
    favs = _read_json(FAVORITES_FILE, [])
    added = False
    if body.voice in favs:
        favs.remove(body.voice)
    else:
        favs.append(body.voice)
        added = True
    _write_json(FAVORITES_FILE, favs)
    from server.app import app_state
    app_state["favorites"] = set(favs)
    return {"favorites": favs, "added": added}


# ── Pronunciations ───────────────────────────────────────────────

@router.get("/pronunciations")
async def get_pronunciations():
    return {"entries": _read_json(PRONUNCIATION_FILE, [])}


@router.post("/pronunciations")
async def add_pronunciation(entry: PronunciationEntry):
    entries = _read_json(PRONUNCIATION_FILE, [])
    entries.append(entry.model_dump())
    _write_json(PRONUNCIATION_FILE, entries)
    return {"entries": entries}


@router.put("/pronunciations/{index}")
async def update_pronunciation(index: int, entry: PronunciationEntry):
    entries = _read_json(PRONUNCIATION_FILE, [])
    if index < 0 or index >= len(entries):
        raise HTTPException(status_code=404, detail="Index out of range")
    entries[index] = entry.model_dump()
    _write_json(PRONUNCIATION_FILE, entries)
    return {"entries": entries}


@router.delete("/pronunciations/{index}")
async def delete_pronunciation(index: int):
    entries = _read_json(PRONUNCIATION_FILE, [])
    if index < 0 or index >= len(entries):
        raise HTTPException(status_code=404, detail="Index out of range")
    entries.pop(index)
    _write_json(PRONUNCIATION_FILE, entries)
    return {"entries": entries}


# ── History ──────────────────────────────────────────────────────

@router.get("/history")
async def get_history(limit: int = 50):
    records = _read_json(HISTORY_FILE, [])
    return {"records": records[-limit:]}


@router.delete("/history")
async def clear_history():
    _write_json(HISTORY_FILE, [])
    return {"ok": True}


# ── System Status ────────────────────────────────────────────────

@router.get("/system/status", response_model=SystemStatus)
async def system_status():
    from server.app import app_state
    cs = cache_size(app_state["cache_dir"])
    return SystemStatus(
        ffmpeg=app_state["ffmpeg"],
        tesseract=app_state["tesseract"],
        cache_size_mb=round(cs["total_bytes"] / (1024 * 1024), 2),
        voice_count=len(app_state.get("voices", [])),
        macos_voices=any(
            v.get("Backend") == "macos"
            for v in app_state.get("voices", [])
        ),
    )


@router.post("/cache/clear")
async def clear_cache():
    import shutil
    from server.app import app_state
    cache_dir = app_state["cache_dir"]
    cs = cache_size(cache_dir)
    freed = cs["total_bytes"]
    for sub in ("previews", "conversions", "jobs"):
        d = os.path.join(cache_dir, sub)
        if os.path.isdir(d):
            shutil.rmtree(d, ignore_errors=True)
    from engine.cache import ensure_cache_dirs
    ensure_cache_dirs(cache_dir)
    return {"ok": True, "freed_mb": round(freed / (1024 * 1024), 2)}
