"""Project save/load routes."""

import json
import os
import time

from fastapi import APIRouter, HTTPException, UploadFile
from fastapi.responses import JSONResponse

from server.config import CACHE_DIR
from server.models import ProjectSave

router = APIRouter(prefix="/api", tags=["projects"])

PROJECTS_DIR = os.path.join(CACHE_DIR, "projects")
os.makedirs(PROJECTS_DIR, exist_ok=True)


@router.post("/projects/save")
async def save_project(req: ProjectSave):
    """Save current project state as a JSON file."""
    project_data = {
        "version": 1,
        "name": req.name,
        "text": req.text,
        "voice": req.voice,
        "speed": req.speed,
        "pitch": req.pitch,
        "volume": req.volume,
        "format": req.format,
        "source_meta": req.source_meta,
        "saved_at": time.time(),
    }

    filename = f"{req.name.replace(' ', '_')}_{int(time.time())}.tts2mp3"
    filepath = os.path.join(PROJECTS_DIR, filename)

    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(project_data, f, indent=2)

    return {"filename": filename, "path": filepath}


@router.post("/projects/load")
async def load_project(file: UploadFile):
    """Load a project file."""
    content = await file.read()
    try:
        data = json.loads(content)
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="Invalid project file")

    if "text" not in data or "voice" not in data:
        raise HTTPException(status_code=400, detail="Invalid project format")

    return data


@router.get("/projects")
async def list_projects():
    """List saved projects."""
    projects = []
    if os.path.isdir(PROJECTS_DIR):
        for f in sorted(os.listdir(PROJECTS_DIR), reverse=True):
            if f.endswith(".tts2mp3"):
                fpath = os.path.join(PROJECTS_DIR, f)
                try:
                    with open(fpath) as fh:
                        data = json.load(fh)
                    projects.append({
                        "filename": f,
                        "name": data.get("name", "Untitled"),
                        "voice": data.get("voice", ""),
                        "saved_at": data.get("saved_at", 0),
                    })
                except Exception:
                    pass
    return {"projects": projects}


@router.delete("/projects/{filename}")
async def delete_project(filename: str):
    """Delete a saved project."""
    fpath = os.path.join(PROJECTS_DIR, filename)
    if not os.path.isfile(fpath):
        raise HTTPException(status_code=404, detail="Project not found")
    os.unlink(fpath)
    return {"ok": True}
