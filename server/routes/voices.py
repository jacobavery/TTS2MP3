"""Voice list, preview, and staff picks routes."""

import os

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import FileResponse

from engine.cache import preview_cache_path
from engine.tts import generate_preview, _run_async
from engine.voices import STAFF_PICKS, filter_voices, voice_display_name

router = APIRouter(prefix="/api/voices", tags=["voices"])


@router.get("")
async def list_voices(
    search: str = "",
    language: str = "All",
    gender: str = "All",
    favorites_only: bool = False,
):
    from server.app import app_state
    favorites = app_state.get("favorites", set())
    voices = filter_voices(
        app_state.get("voices", []),
        search=search,
        language=language,
        gender=gender,
        favorites=favorites,
        favorites_only=favorites_only,
    )
    return {
        "voices": voices,
        "count": len(voices),
    }


@router.get("/staff-picks")
async def staff_picks():
    return {"picks": STAFF_PICKS}


@router.get("/preview/{voice_name}")
async def voice_preview(voice_name: str):
    from server.app import app_state
    cache_dir = app_state["cache_dir"]
    path = preview_cache_path(voice_name, cache_dir)

    if not os.path.isfile(path):
        # Generate preview
        os.makedirs(os.path.dirname(path), exist_ok=True)
        try:
            await generate_preview(voice_name, path)
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Preview failed: {e}")

    if not os.path.isfile(path):
        raise HTTPException(status_code=404, detail="Preview not available")

    return FileResponse(path, media_type="audio/mpeg")


@router.get("/languages")
async def voice_languages():
    from server.app import app_state
    from engine.voices import LANG_NAMES
    voices = app_state.get("voices", [])
    locales = sorted(set(v.get("Locale", "") for v in voices))
    result = []
    for loc in locales:
        lang_code = loc.split("-")[0] if loc else ""
        name = LANG_NAMES.get(lang_code, loc)
        result.append({"locale": loc, "name": name})
    return {"languages": result}
