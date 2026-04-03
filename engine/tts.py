"""Core TTS synthesis engine: edge_tts cloud + macOS say offline."""
from __future__ import annotations

import asyncio
import os
import shutil
import subprocess
import tempfile
import time
from typing import Callable

import edge_tts

from .audio import (
    check_ffmpeg, concat_audio, convert_format, embed_metadata,
    make_silence_clip, normalize_loudness,
)
from .cache import cache_key, conv_cache_path, ensure_cache_dirs
from .formats import EXPORT_FORMATS, PARA_PAUSE_OPTIONS, QUALITY_PRESETS
from .text import apply_pronunciations, chunk_text, normalize_text

MAX_RETRIES = 3


def _run_async(coro):
    """Run an async coroutine in a new event loop (for use from sync code)."""
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


async def generate_preview(voice_name: str, out_path: str):
    """Generate a voice preview MP3."""
    await edge_tts.Communicate(
        "Hello! This is a preview of this voice. How does it sound?",
        voice_name,
    ).save(out_path)


def synthesize_macos(
    text: str,
    voice_name: str,
    out_path: str,
    rate: str = "+0%",
    ffmpeg_available: bool = True,
    cache_dir: str = ".tts_cache",
):
    """Synthesise *text* using the macOS `say` command and write MP3 to *out_path*."""
    wpm = 175
    try:
        pct = int(rate.rstrip("%"))
        wpm = max(80, min(500, int(175 * (1 + pct / 100))))
    except ValueError:
        pass

    say_name = voice_name
    if ":" in voice_name:
        say_name = voice_name.split(":", 1)[1]
    if say_name.startswith("macos."):
        say_name = say_name[6:]

    conv_dir = os.path.join(cache_dir, "conversions")
    os.makedirs(conv_dir, exist_ok=True)

    aiff_fd, aiff_tmp = tempfile.mkstemp(suffix=".aiff", dir=conv_dir)
    os.close(aiff_fd)
    try:
        txt_fd, txt_tmp = tempfile.mkstemp(suffix=".txt", dir=conv_dir)
        try:
            with os.fdopen(txt_fd, "w", encoding="utf-8") as tf:
                tf.write(text)
            result = subprocess.run(
                ["say", "-v", say_name, "-r", str(wpm), "-f", txt_tmp, "-o", aiff_tmp],
                capture_output=True,
            )
            if result.returncode != 0:
                raise RuntimeError(
                    "say command failed: "
                    + result.stderr.decode(errors="replace")[:300])
        finally:
            try:
                os.unlink(txt_tmp)
            except OSError:
                pass

        if not os.path.isfile(aiff_tmp) or os.path.getsize(aiff_tmp) == 0:
            raise RuntimeError("macOS say produced no audio output.")

        if ffmpeg_available:
            res = subprocess.run(
                ["ffmpeg", "-y", "-i", aiff_tmp,
                 "-acodec", "libmp3lame", "-b:a", "192k", out_path],
                capture_output=True,
            )
            if res.returncode != 0:
                raise RuntimeError(
                    "ffmpeg AIFF->MP3 failed: "
                    + res.stderr.decode(errors="replace")[:300])
        else:
            shutil.copy2(aiff_tmp, out_path)
    finally:
        try:
            os.unlink(aiff_tmp)
        except OSError:
            pass


def _synthesize_chunk(
    text: str,
    voice_name: str,
    out_path: str,
    backend: str,
    rate: str,
    pitch: str,
    volume: str,
    ffmpeg_available: bool,
    cache_dir: str,
):
    """Synthesise one text chunk to out_path; retry up to MAX_RETRIES times."""
    conv_dir = os.path.join(cache_dir, "conversions")
    ck_fd, ck_tmp = tempfile.mkstemp(suffix=".mp3", dir=conv_dir)
    os.close(ck_fd)
    last_err = None
    for attempt in range(MAX_RETRIES):
        try:
            if backend == "macos":
                synthesize_macos(
                    text, voice_name, ck_tmp,
                    rate=rate,
                    ffmpeg_available=ffmpeg_available,
                    cache_dir=cache_dir,
                )
            else:
                async def _stream(ct=text, p=ck_tmp):
                    with open(p, "wb") as f:
                        async for part in edge_tts.Communicate(
                            ct, voice_name,
                            rate=rate, pitch=pitch, volume=volume,
                        ).stream():
                            if part["type"] == "audio":
                                f.write(part["data"])
                _run_async(_stream())

            if os.path.isfile(ck_tmp) and os.path.getsize(ck_tmp) > 0:
                shutil.move(ck_tmp, out_path)
                return
            last_err = RuntimeError("synthesis returned no audio data")
        except Exception as e:
            last_err = e
            if attempt < MAX_RETRIES - 1:
                time.sleep(2 ** attempt)
        finally:
            if os.path.isfile(ck_tmp):
                try:
                    os.unlink(ck_tmp)
                except OSError:
                    pass
    raise RuntimeError(f"Synthesis failed after {MAX_RETRIES} attempts: {last_err}")


def convert_text_to_audio(
    text: str,
    voice_name: str,
    out_path: str,
    fmt: str,
    backend: str = "edge_tts",
    rate: str = "+0%",
    pitch: str = "+0Hz",
    volume: str = "+0%",
    do_normalize_text: bool = False,
    do_normalize_audio: bool = False,
    para_pause: float = 0.0,
    quality_preset: str = "",
    pronunciations: list[dict] | None = None,
    metadata: dict | None = None,
    cache_dir: str = ".tts_cache",
    ffmpeg_available: bool = True,
    progress_cb: Callable[[int], None] | None = None,
):
    """
    Full conversion pipeline: preprocess -> chunk -> synthesize -> concat ->
    format convert -> normalize -> embed metadata.
    """
    ensure_cache_dirs(cache_dir)
    conv_dir = os.path.join(cache_dir, "conversions")

    # Pre-processing
    if pronunciations:
        text = apply_pronunciations(text, pronunciations)
    if do_normalize_text:
        text = normalize_text(text)

    chunks = chunk_text(text)
    n = len(chunks)

    # Resolve quality preset
    quality_extra = []
    if quality_preset:
        for label, args in QUALITY_PRESETS.get(fmt, []):
            if label == quality_preset:
                quality_extra = args
                break

    tmp_dir = None
    tmp_mp3 = None

    try:
        key = cache_key(voice_name, text, rate, pitch, volume)
        cache_mp3 = conv_cache_path(key, cache_dir)

        if os.path.isfile(cache_mp3) and os.path.getsize(cache_mp3) > 0:
            if progress_cb:
                progress_cb(70)
        elif n == 1 and para_pause == 0.0:
            # Single-chunk, no silence
            total = len(text)
            done = 0
            tmp_fd, tmp_mp3 = tempfile.mkstemp(suffix=".mp3", dir=conv_dir)
            os.close(tmp_fd)

            if backend == "macos":
                _synthesize_chunk(
                    text, voice_name, tmp_mp3, backend,
                    rate, pitch, volume, ffmpeg_available, cache_dir,
                )
            else:
                async def stream():
                    nonlocal done
                    with open(tmp_mp3, "wb") as f:
                        async for chunk in edge_tts.Communicate(
                            text, voice_name, rate=rate, pitch=pitch, volume=volume,
                        ).stream():
                            if chunk["type"] == "audio":
                                f.write(chunk["data"])
                            elif chunk["type"] == "WordBoundary":
                                done = min(total, done + len(chunk.get("text", "")) + 1)
                                if progress_cb:
                                    progress_cb(min(80, int(done / total * 80)))
                _run_async(stream())

            if not (os.path.isfile(tmp_mp3) and os.path.getsize(tmp_mp3) > 0):
                raise RuntimeError("TTS synthesis returned no audio data.")

            shutil.move(tmp_mp3, cache_mp3)
            tmp_mp3 = None
        else:
            # Multi-chunk (or silence needed)
            tmp_dir = tempfile.mkdtemp(dir=conv_dir)
            chunk_files = []

            silence_path = None
            if para_pause > 0.0 and ffmpeg_available:
                silence_path = os.path.join(tmp_dir, "silence.mp3")
                make_silence_clip(para_pause, silence_path)

            for ci, ct in enumerate(chunks):
                ck = cache_key(voice_name, ct, rate, pitch, volume)
                ck_path = conv_cache_path(ck, cache_dir)

                if not (os.path.isfile(ck_path) and os.path.getsize(ck_path) > 0):
                    _synthesize_chunk(
                        ct, voice_name, ck_path, backend,
                        rate, pitch, volume, ffmpeg_available, cache_dir,
                    )

                chunk_files.append(ck_path)
                if silence_path and ci < n - 1:
                    chunk_files.append(silence_path)
                if progress_cb:
                    progress_cb(min(80, int((ci + 1) / n * 80)))

            # Concat all chunks (or just copy if single file / no ffmpeg)
            if len(chunk_files) == 1 or not ffmpeg_available:
                if os.path.abspath(chunk_files[0]) != os.path.abspath(cache_mp3):
                    shutil.copy2(chunk_files[0], cache_mp3)
            else:
                cfd, concat_tmp = tempfile.mkstemp(suffix=".mp3", dir=conv_dir)
                os.close(cfd)
                concat_audio(chunk_files, concat_tmp, tmp_dir)
                shutil.move(concat_tmp, cache_mp3)

        if progress_cb:
            progress_cb(88)

        # Format conversion
        convert_format(cache_mp3, out_path, fmt, quality_extra or None,
                       ffmpeg_available=ffmpeg_available)

        if not os.path.isfile(out_path) or os.path.getsize(out_path) == 0:
            raise RuntimeError(f"Output file is missing or empty: {out_path}")

        if progress_cb:
            progress_cb(92)

        # Audio normalization
        if do_normalize_audio and ffmpeg_available:
            normalize_loudness(out_path, conv_dir)

        if progress_cb:
            progress_cb(96)

        # Metadata embedding
        if metadata and ffmpeg_available:
            embed_metadata(
                out_path,
                title=metadata.get("title", ""),
                author=metadata.get("author", ""),
                cover_path=metadata.get("cover_path"),
            )

        if progress_cb:
            progress_cb(100)

    finally:
        if tmp_mp3 and os.path.isfile(tmp_mp3):
            try:
                os.unlink(tmp_mp3)
            except OSError:
                pass
        if tmp_dir:
            shutil.rmtree(tmp_dir, ignore_errors=True)
