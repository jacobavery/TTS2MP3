"""Voice comparison route: synthesize same text with multiple voices."""

import asyncio
import os

from fastapi import APIRouter, HTTPException

from engine.tts import convert_text_to_audio
from server.models import CompareRequest

router = APIRouter(prefix="/api", tags=["compare"])


@router.post("/voices/compare")
async def compare_voices(req: CompareRequest):
    """Synthesize the same text with up to 6 voices and return download URLs."""
    from server.app import app_state

    if not req.text.strip():
        raise HTTPException(status_code=400, detail="Text is required")
    if len(req.voices) < 2:
        raise HTTPException(status_code=400, detail="At least 2 voices required")
    if len(req.voices) > 6:
        raise HTTPException(status_code=400, detail="Maximum 6 voices")

    # Resolve backends
    voice_backends = {}
    for v in app_state.get("voices", []):
        voice_backends[v["ShortName"]] = v.get("Backend", "edge_tts")

    job_mgr = app_state["job_manager"]
    jobs = []

    loop = asyncio.get_event_loop()

    for voice_name in req.voices:
        job = job_mgr.create_job(output_filename=f"{voice_name}.mp3")
        jobs.append((voice_name, job))

        async def run(v=voice_name, j=job):
            async with app_state["semaphore"]:
                j.status = "running"
                backend = voice_backends.get(v, "edge_tts")
                try:
                    await loop.run_in_executor(
                        None,
                        lambda: convert_text_to_audio(
                            text=req.text,
                            voice_name=v,
                            out_path=j.output_path,
                            fmt="MP3",
                            backend=backend,
                            cache_dir=app_state["cache_dir"],
                            ffmpeg_available=app_state["ffmpeg"],
                        ),
                    )
                    j.status = "done"
                    j.progress = 100
                except Exception as e:
                    j.status = "error"
                    j.error = str(e)
                finally:
                    loop.call_soon_threadsafe(j.queue.put_nowait, None)

        asyncio.create_task(run())

    return {
        "jobs": [
            {"voice": name, "job_id": job.id}
            for name, job in jobs
        ]
    }
