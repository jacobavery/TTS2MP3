"""Single conversion and job tracking routes."""

import asyncio
import json
import os
import time

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse

from engine.formats import EXPORT_FORMATS
from engine.tts import convert_text_to_audio
from server.config import HISTORY_FILE, MAX_TEXT_LENGTH
from server.models import ConvertRequest, ConvertResponse, JobStatus
from server.sse import sse_response

router = APIRouter(prefix="/api", tags=["convert"])


def _save_history(req: ConvertRequest):
    """Append a conversion record to history."""
    try:
        records = []
        if os.path.isfile(HISTORY_FILE):
            with open(HISTORY_FILE) as f:
                records = json.load(f)
        records.append({
            "text": req.text[:200],
            "voice": req.voice,
            "format": req.format,
            "quality": req.quality,
            "timestamp": time.time(),
        })
        # Keep last 200 records
        records = records[-200:]
        with open(HISTORY_FILE, "w") as f:
            json.dump(records, f, indent=2)
    except Exception:
        pass


@router.post("/convert", response_model=ConvertResponse)
async def start_conversion(req: ConvertRequest):
    from server.app import app_state

    if len(req.text) > MAX_TEXT_LENGTH:
        raise HTTPException(status_code=400, detail="Text exceeds maximum length")

    if req.format not in EXPORT_FORMATS:
        raise HTTPException(status_code=400, detail=f"Unknown format: {req.format}")

    # Resolve voice backend
    backend = "edge_tts"
    for v in app_state.get("voices", []):
        if v["ShortName"] == req.voice:
            backend = v.get("Backend", "edge_tts")
            break

    ext = EXPORT_FORMATS[req.format][0]
    job_mgr = app_state["job_manager"]
    job = job_mgr.create_job(output_filename=f"output{ext}")

    loop = asyncio.get_event_loop()
    progress_cb = job_mgr.make_progress_cb(job, loop)

    async def run():
        async with app_state["semaphore"]:
            job.status = "running"
            try:
                await loop.run_in_executor(
                    None,
                    lambda: convert_text_to_audio(
                        text=req.text,
                        voice_name=req.voice,
                        out_path=job.output_path,
                        fmt=req.format,
                        backend=backend,
                        rate=req.rate,
                        pitch=req.pitch,
                        volume=req.volume,
                        do_normalize_text=req.normalize_text,
                        do_normalize_audio=req.normalize_audio,
                        para_pause=req.para_pause,
                        quality_preset=req.quality,
                        pronunciations=req.pronunciations or None,
                        cache_dir=app_state["cache_dir"],
                        ffmpeg_available=app_state["ffmpeg"],
                        progress_cb=progress_cb,
                    ),
                )
                job.status = "done"
                job.progress = 100
                # Save to history
                _save_history(req)
                loop.call_soon_threadsafe(
                    job.queue.put_nowait,
                    {"event": "done", "download_url": f"/api/jobs/{job.id}/download"},
                )
            except Exception as e:
                job.status = "error"
                job.error = str(e)
                loop.call_soon_threadsafe(
                    job.queue.put_nowait,
                    {"event": "error", "error": str(e)},
                )
            finally:
                loop.call_soon_threadsafe(job.queue.put_nowait, None)

    asyncio.create_task(run())
    return ConvertResponse(job_id=job.id)


@router.get("/jobs/{job_id}", response_model=JobStatus)
async def get_job_status(job_id: str):
    from server.app import app_state
    job = app_state["job_manager"].get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return JobStatus(
        job_id=job.id,
        status=job.status,
        progress=job.progress,
        error=job.error,
        download_url=f"/api/jobs/{job.id}/download" if job.status == "done" else None,
    )


@router.get("/jobs/{job_id}/stream")
async def job_stream(job_id: str):
    from server.app import app_state
    job = app_state["job_manager"].get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return sse_response(job.queue)


@router.get("/jobs/{job_id}/download")
async def job_download(job_id: str):
    from server.app import app_state
    job = app_state["job_manager"].get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    if job.status != "done":
        raise HTTPException(status_code=400, detail="Job not complete")
    if not job.output_path or not os.path.isfile(job.output_path):
        raise HTTPException(status_code=404, detail="Output file not found")
    return FileResponse(
        job.output_path,
        filename=job.output_filename,
        media_type="application/octet-stream",
    )
