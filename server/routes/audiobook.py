"""Audiobook builder routes: EPUB chapter extraction and M4B conversion."""

import asyncio
import os
import tempfile

from fastapi import APIRouter, HTTPException, UploadFile

from engine.audiobook import epub_chapters, assemble_m4b
from engine.readers import epub_metadata
from engine.tts import convert_text_to_audio
from server.config import MAX_UPLOAD_SIZE

router = APIRouter(prefix="/api", tags=["audiobook"])


@router.post("/audiobook/chapters")
async def get_chapters(file: UploadFile):
    """Upload an EPUB and return its chapter list."""
    from server.app import app_state

    ext = os.path.splitext(file.filename or "")[1].lower()
    if ext != ".epub":
        raise HTTPException(status_code=400, detail="Only EPUB files are supported")

    content = await file.read()
    if len(content) > MAX_UPLOAD_SIZE:
        raise HTTPException(status_code=400, detail="File exceeds 50 MB limit")

    fd, tmp_path = tempfile.mkstemp(suffix=".epub")
    try:
        with os.fdopen(fd, "wb") as f:
            f.write(content)

        chapters = epub_chapters(tmp_path)
        try:
            metadata = epub_metadata(tmp_path)
        except Exception:
            metadata = {}

        # Store epub path for later conversion
        app_state.setdefault("_epub_temps", {})[tmp_path] = True

        return {
            "epub_path": tmp_path,
            "chapters": [
                {"index": i, "title": title, "words": len(text.split()), "chars": len(text)}
                for i, (title, text) in enumerate(chapters)
            ],
            "metadata": metadata,
        }
    except Exception as e:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass
        raise HTTPException(status_code=500, detail=f"Failed to parse EPUB: {e}")


@router.post("/audiobook/convert")
async def convert_audiobook(req: dict):
    """Convert selected EPUB chapters to M4B audiobook."""
    from server.app import app_state

    epub_path = req.get("epub_path", "")
    selected = req.get("selected_chapters", [])
    voice = req.get("voice", "")
    rate = req.get("rate", "+0%")
    pitch = req.get("pitch", "+0Hz")
    volume = req.get("volume", "+0%")

    if not epub_path or not os.path.isfile(epub_path):
        raise HTTPException(status_code=400, detail="EPUB file not found. Please re-upload.")
    if not voice:
        raise HTTPException(status_code=400, detail="Voice is required")
    if not selected:
        raise HTTPException(status_code=400, detail="Select at least one chapter")

    # Parse chapters
    chapters = epub_chapters(epub_path)
    if not chapters:
        raise HTTPException(status_code=400, detail="No chapters found")

    # Filter selected
    chosen = [(chapters[i][0], chapters[i][1]) for i in selected if i < len(chapters)]
    if not chosen:
        raise HTTPException(status_code=400, detail="No valid chapters selected")

    # Resolve backend
    backend = "edge_tts"
    for v in app_state.get("voices", []):
        if v["ShortName"] == voice:
            backend = v.get("Backend", "edge_tts")
            break

    job_mgr = app_state["job_manager"]
    job = job_mgr.create_job(output_filename="audiobook.m4b")
    loop = asyncio.get_event_loop()

    async def run():
        async with app_state["semaphore"]:
            job.status = "running"
            chapter_mp3s = []
            chapter_titles = []
            try:
                total = len(chosen)
                for idx, (title, text) in enumerate(chosen):
                    chapter_titles.append(title)
                    ch_path = os.path.join(os.path.dirname(job.output_path), f"ch_{idx:03d}.mp3")

                    def progress_cb(pct, _idx=idx, _total=total):
                        overall = int((_idx * 100 + pct) / _total)
                        job.progress = min(overall, 99)
                        loop.call_soon_threadsafe(
                            job.queue.put_nowait, {"pct": job.progress}
                        )

                    await loop.run_in_executor(
                        None,
                        lambda t=text, p=ch_path, cb=progress_cb: convert_text_to_audio(
                            text=t,
                            voice_name=voice,
                            out_path=p,
                            fmt="MP3",
                            backend=backend,
                            rate=rate,
                            pitch=pitch,
                            volume=volume,
                            cache_dir=app_state["cache_dir"],
                            ffmpeg_available=app_state["ffmpeg"],
                            progress_cb=cb,
                        ),
                    )
                    chapter_mp3s.append(ch_path)

                # Assemble M4B
                if app_state["ffmpeg"]:
                    await loop.run_in_executor(
                        None,
                        lambda: assemble_m4b(chapter_mp3s, chapter_titles, job.output_path),
                    )
                else:
                    raise RuntimeError("ffmpeg is required for M4B assembly")

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
