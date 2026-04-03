"""Batch conversion routes."""

import asyncio
import json
import os
import time
import uuid

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse

from engine.formats import EXPORT_FORMATS
from engine.tts import convert_text_to_audio
from server.config import HISTORY_FILE, MAX_TEXT_LENGTH
from server.models import BatchRequest, BatchResponse, JobStatus
from server.sse import sse_response

router = APIRouter(prefix="/api", tags=["batch"])


@router.post("/batch/convert", response_model=BatchResponse)
async def start_batch(req: BatchRequest):
    from server.app import app_state

    if req.format not in EXPORT_FORMATS:
        raise HTTPException(status_code=400, detail=f"Unknown format: {req.format}")
    if len(req.items) > 20:
        raise HTTPException(status_code=400, detail="Maximum 20 items per batch")

    backend = "edge_tts"
    for v in app_state.get("voices", []):
        if v["ShortName"] == req.voice:
            backend = v.get("Backend", "edge_tts")
            break

    ext = EXPORT_FORMATS[req.format][0]
    job_mgr = app_state["job_manager"]
    batch_id = uuid.uuid4().hex[:12]
    job_ids = []

    loop = asyncio.get_event_loop()

    for item in req.items:
        if len(item.text) > MAX_TEXT_LENGTH:
            continue

        job = job_mgr.create_job(
            output_filename=f"{os.path.splitext(item.filename)[0]}{ext}"
        )
        job_ids.append(job.id)

        async def run(j=job, txt=item.text, fname=item.filename):
            async with app_state["semaphore"]:
                j.status = "running"
                progress_cb = job_mgr.make_progress_cb(j, loop)
                try:
                    await loop.run_in_executor(
                        None,
                        lambda: convert_text_to_audio(
                            text=txt,
                            voice_name=req.voice,
                            out_path=j.output_path,
                            fmt=req.format,
                            backend=backend,
                            rate=req.rate,
                            pitch=req.pitch,
                            volume=req.volume,
                            do_normalize_text=req.normalize_text,
                            do_normalize_audio=req.normalize_audio,
                            para_pause=req.para_pause,
                            quality_preset=req.quality,
                            cache_dir=app_state["cache_dir"],
                            ffmpeg_available=app_state["ffmpeg"],
                            progress_cb=progress_cb,
                        ),
                    )
                    j.status = "done"
                    j.progress = 100
                    loop.call_soon_threadsafe(
                        j.queue.put_nowait,
                        {"event": "done", "download_url": f"/api/jobs/{j.id}/download"},
                    )
                except Exception as e:
                    j.status = "error"
                    j.error = str(e)
                    loop.call_soon_threadsafe(
                        j.queue.put_nowait,
                        {"event": "error", "error": str(e)},
                    )
                finally:
                    loop.call_soon_threadsafe(j.queue.put_nowait, None)

        asyncio.create_task(run())

    return BatchResponse(batch_id=batch_id, job_ids=job_ids)


@router.get("/batch/status")
async def batch_status(job_ids: str):
    """Get status of multiple jobs. job_ids is comma-separated."""
    from server.app import app_state
    ids = [j.strip() for j in job_ids.split(",") if j.strip()]
    results = []
    for jid in ids:
        job = app_state["job_manager"].get_job(jid)
        if job:
            results.append({
                "job_id": job.id,
                "status": job.status,
                "progress": job.progress,
                "error": job.error,
                "download_url": f"/api/jobs/{job.id}/download" if job.status == "done" else None,
                "filename": job.output_filename,
            })
    return {"jobs": results}
