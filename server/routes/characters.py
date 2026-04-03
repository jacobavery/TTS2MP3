"""Character detection and multi-voice conversion routes."""

import asyncio
import os

from fastapi import APIRouter, HTTPException

from engine.characters import detect_characters, parse_segments
from engine.formats import EXPORT_FORMATS
from engine.tts import convert_text_to_audio
from engine.audio import concat_audio
from server.models import CharacterDetectRequest, CharacterConvertRequest

router = APIRouter(prefix="/api", tags=["characters"])


@router.post("/characters/detect")
async def detect(req: CharacterDetectRequest):
    """Find CHARACTER: patterns in text."""
    characters = detect_characters(req.text)
    return {"characters": characters}


@router.post("/characters/convert")
async def convert(req: CharacterConvertRequest):
    """Multi-voice conversion: each character uses a different voice."""
    from server.app import app_state

    if req.format not in EXPORT_FORMATS:
        raise HTTPException(status_code=400, detail=f"Unknown format: {req.format}")

    segments = parse_segments(req.text, req.assignments, req.default_voice)
    if not segments:
        raise HTTPException(status_code=400, detail="No segments found")

    # Resolve backends for all voices used
    voice_backends = {}
    for v in app_state.get("voices", []):
        voice_backends[v["ShortName"]] = v.get("Backend", "edge_tts")

    ext = EXPORT_FORMATS[req.format][0]
    job_mgr = app_state["job_manager"]
    job = job_mgr.create_job(output_filename=f"multi_voice{ext}")
    loop = asyncio.get_event_loop()

    async def run():
        async with app_state["semaphore"]:
            job.status = "running"
            seg_files = []
            try:
                total = len(segments)
                for idx, (voice_name, seg_text) in enumerate(segments):
                    seg_path = os.path.join(
                        os.path.dirname(job.output_path), f"seg_{idx:04d}.mp3"
                    )
                    backend = voice_backends.get(voice_name, "edge_tts")

                    def progress_cb(pct, _idx=idx, _total=total):
                        overall = int((_idx * 100 + pct) / _total)
                        job.progress = min(overall, 99)
                        loop.call_soon_threadsafe(
                            job.queue.put_nowait, {"pct": job.progress}
                        )

                    await loop.run_in_executor(
                        None,
                        lambda t=seg_text, v=voice_name, p=seg_path, b=backend, cb=progress_cb: convert_text_to_audio(
                            text=t,
                            voice_name=v,
                            out_path=p,
                            fmt="MP3",
                            backend=b,
                            rate=req.rate,
                            pitch=req.pitch,
                            volume=req.volume,
                            cache_dir=app_state["cache_dir"],
                            ffmpeg_available=app_state["ffmpeg"],
                            progress_cb=cb,
                        ),
                    )
                    seg_files.append(seg_path)

                # Concat all segments
                if len(seg_files) > 1 and app_state["ffmpeg"]:
                    tmp_dir = os.path.dirname(job.output_path)
                    await loop.run_in_executor(
                        None,
                        lambda: concat_audio(seg_files, job.output_path, tmp_dir),
                    )
                elif seg_files:
                    import shutil
                    shutil.copy2(seg_files[0], job.output_path)

                job.status = "done"
                job.progress = 100
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
    return {"job_id": job.id}
